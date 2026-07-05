#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
traduzir.py  -  Fluxo de traducao PT-BR do Fallout com checkpoint.

Ideia central:
  * Cada arquivo do jogo vira uma PASTA propria.
  * Dentro dela ficam SEMPRE dois arquivos, separados:
        en.msg  -> o ingles (referencia, nao edite)
        pt.msg  -> a traducao (VOCE edita aqui)
  * No pt.msg, tudo que ainda NAO foi traduzido continua em INGLES.
    Ou seja: o ingles esta sempre la, pronto pra voce continuar.
  * Quando terminar de mexer, roda:   python3 traduzir.py
        - gera um JSON com o que mudou (traducao/alteracoes.json)
        - SALVA o ponto onde voce parou (traducao/progresso.json)
  * Da proxima vez, roda 'python3 traduzir.py continuar' e ele te diz
    exatamente de onde retomar (proximas falas ainda em ingles).

Como o programa sabe o que ja foi traduzido?
  Simples: no pt.msg, uma fala IGUAL ao ingles = ainda pendente.
  Assim que voce troca o texto, ela passa a contar como traduzida.

Comandos:
  init        Cria a arvore de pastas (en.msg + pt.msg) a partir dos originais.
  (sem nada)  Igual a 'salvar': varre tudo, gera o JSON e salva o checkpoint.
  salvar      Mesmo que rodar sem argumento.
  status      Mostra o progresso (traduzido / pendente).
  continuar   Mostra de onde retomar (proximas falas ainda em ingles).
  compilar    Gera os .msg finais do jogo (ISO-8859-1) em traducao/saida_jogo/.
"""

import os, re, sys, json, glob, time, argparse

# --------------------------------------------------------------------------
RAIZ       = "traducao"
DIR_ARQ    = os.path.join(RAIZ, "arquivos")     # a arvore de pastas por-arquivo
DIR_JOGO   = os.path.join(RAIZ, "saida_jogo")   # saida final pro jogo
PROGRESSO  = os.path.join(RAIZ, "progresso.json")
ALTERACOES = os.path.join(RAIZ, "alteracoes.json")

# Estrutura do mod que o jogo le, igual a da traducao tcheca:
#   fo1_lang_brazilian/text/brazilian/{dialog,game,cuts}/ARQUIVO.msg
# (a tcheca usa fo1_lang_czech/text/czech/...). Da pra trocar via --mod/--lang.
MOD_PADRAO  = "fo1_lang_brazilian"
LANG_PADRAO = "brazilian"

RE_MSG   = re.compile(r'\{(\d+)\}\{(.*?)\}\{(.*?)\}', re.DOTALL)
RE_CUTS  = re.compile(r'^(\d+):(.*)$')
# Tokens de formato reais do jogo sao %s / %d / %% (sem espaco entre % e a letra).
# Nao incluir espaco na classe evita falso positivo com porcentagem em prosa
# (ex.: "5% chance" nao e um token, mas "%d" e).
RE_TOKEN = re.compile(r'%[-+0-9.#]*[sdifgxXceEo%]')

# --------------------------------------------------------------------------
# I/O basico
# --------------------------------------------------------------------------
def ler_txt(caminho, enc="utf-8"):
    with open(caminho, "rb") as f:
        return f.read().decode(enc)

def ler_jogo(caminho):
    """Le um arquivo original do jogo (ISO-8859-1) e devolve texto unicode."""
    with open(caminho, "rb") as f:
        return f.read().decode("iso-8859-1")

def escrever(caminho, texto, enc="utf-8"):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb") as f:
        f.write(texto.encode(enc))

# --------------------------------------------------------------------------
# Parsers de formato
# --------------------------------------------------------------------------
def parse(texto, tipo):
    """Devolve lista ordenada de dicts {id, audio, texto}."""
    itens = []
    if tipo == "braced":
        for m in RE_MSG.finditer(texto):
            itens.append({"id": m.group(1), "audio": m.group(2), "texto": m.group(3)})
    else:
        for linha in texto.split("\n"):
            m = RE_CUTS.match(linha.rstrip("\r"))
            if m:
                itens.append({"id": m.group(1), "audio": "", "texto": m.group(2)})
    return itens

def montar(entradas, tipo):
    """Reconstroi o conteudo de um arquivo a partir das entradas."""
    linhas = []
    for e in entradas:
        if tipo == "braced":
            linhas.append("{%s}{%s}{%s}" % (e["id"], e.get("audio", ""), e["texto"]))
        else:
            linhas.append("%s:%s" % (e["id"], e["texto"]))
    return "\n".join(linhas) + "\n"

def tipo_de(rel):
    p = ("/" + rel.lower().replace("\\", "/"))
    return "numerado" if "/cuts/" in p else "braced"

def categoria(rel):
    p = "/" + rel.lower().replace("\\", "/")
    for c in ("dialog", "cuts", "game", "premade"):
        if "/%s/" % c in p:
            return c
    return "outros"

def nome_base(caminho):
    return os.path.splitext(os.path.basename(caminho))[0].upper()

# --------------------------------------------------------------------------
# Descoberta
# --------------------------------------------------------------------------
EXT_OK = (".msg", ".txt")
EXT_NAO = (".sve", ".bio", ".ini")

def listar(raiz):
    out = []
    for p in glob.glob(os.path.join(raiz, "**", "*"), recursive=True):
        if not os.path.isfile(p):
            continue
        partes = p.lower().replace("\\", "/").split("/")
        if "backup" in partes:
            continue
        if p.lower().endswith(EXT_NAO):
            continue
        if p.lower().endswith(EXT_OK):
            out.append(p)
    return sorted(out)

def indexar_pt(dir_pt):
    idx = {}
    for p in listar(dir_pt):
        idx.setdefault((categoria(p), nome_base(p)), p)
    return idx

# --------------------------------------------------------------------------
# Estado de uma fala
# --------------------------------------------------------------------------
def status_fala(en, pt):
    """
    en/pt = textos da fala. Devolve: 'vazio', 'pendente', 'traduzido' ou 'extra'.
    Regra: pt IGUAL ao en (e en nao vazio) = ainda pendente.
    """
    if en is None:
        return "extra"                 # existe so no PT
    if en.strip() == "":
        return "vazio"                 # {id}{}{} sem texto no jogo
    if pt == en:
        return "pendente"              # ainda em ingles
    return "traduzido"

# --------------------------------------------------------------------------
# INIT - cria a arvore de pastas
# --------------------------------------------------------------------------
def cmd_init(args):
    en_files = listar(args.en)
    pt_idx   = indexar_pt(args.pt)
    if not en_files:
        print("ERRO: nenhum .msg/.txt em", args.en); sys.exit(1)

    prog = {"gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "parou_em": None, "arquivos": {}}
    n_dir = n_pt_criado = n_pt_mantido = 0
    tot_pend = tot_trad = tot_vazio = tot_extra = 0

    for en_path in en_files:
        rel   = os.path.relpath(en_path, args.en).replace("\\", "/")
        cat   = categoria(en_path)
        tipo  = tipo_de(rel)
        ext   = os.path.splitext(en_path)[1].lower()
        nome  = os.path.splitext(os.path.basename(en_path))[0]
        chave = "%s/%s" % (cat, nome)                  # ex.: dialog/ABEL

        s_en = ler_jogo(en_path)
        ent_en = parse(s_en, tipo)

        # traducao existente
        pt_map = {}
        pt_path = pt_idx.get((cat, nome_base(en_path)))
        if pt_path:
            for it in parse(ler_jogo(pt_path), tipo):
                pt_map.setdefault(it["id"], it["texto"])

        # monta pt.msg: PT quando existe/nao-vazio; senao, o proprio ingles
        ent_pt = []
        registro = {}
        ids_en = set()
        for it in ent_en:
            _id = it["id"]; ids_en.add(_id)
            en_txt = it["texto"]
            if _id in pt_map and pt_map[_id].strip() != "":
                pt_txt = pt_map[_id]
            else:
                pt_txt = en_txt                        # nao traduzido = ingles
            ent_pt.append({"id": _id, "audio": it["audio"], "texto": pt_txt})
            st = status_fala(en_txt, pt_txt)
            registro[_id] = {"en": en_txt, "pt": pt_txt, "audio": it["audio"], "status": st}
            if   st == "pendente":  tot_pend += 1
            elif st == "traduzido": tot_trad += 1
            elif st == "vazio":     tot_vazio += 1

        # extras: ids que so existem no PT
        extras = [i for i in pt_map if i not in ids_en]
        for _id in extras:
            ent_pt.append({"id": _id, "audio": "", "texto": pt_map[_id]})
            registro["EX:" + _id] = {"en": None, "pt": pt_map[_id], "audio": "", "status": "extra"}
            tot_extra += 1

        base_dir = os.path.join(DIR_ARQ, cat, nome)
        en_out = os.path.join(base_dir, "en" + ext)
        pt_out = os.path.join(base_dir, "pt" + ext)

        # en sempre (re)escrito verbatim (referencia); pt so se nao existir
        escrever(en_out, s_en)
        if os.path.exists(pt_out) and not args.forcar:
            n_pt_mantido += 1
        else:
            escrever(pt_out, montar(ent_pt, tipo))
            n_pt_criado += 1
        n_dir += 1

        prog["arquivos"][chave] = {
            "origem": rel, "tipo": tipo, "ext": ext,
            "en_rel": os.path.relpath(en_out, RAIZ).replace("\\", "/"),
            "pt_rel": os.path.relpath(pt_out, RAIZ).replace("\\", "/"),
            "ids": registro,
        }

    escrever(PROGRESSO, json.dumps(prog, ensure_ascii=False, indent=1))
    print("INIT concluido.")
    print("  pastas de arquivo criadas    : %d" % n_dir)
    print("  pt criados / mantidos        : %d / %d" % (n_pt_criado, n_pt_mantido))
    print("  ja traduzido                 : %d" % tot_trad)
    print("  pendente (ainda em ingles)   : %d" % tot_pend)
    print("  vazias no jogo (ignorar)     : %d" % tot_vazio)
    print("  extras preservados (PT-only) : %d" % tot_extra)
    print("  arvore em                    : %s/" % DIR_ARQ)
    print("\n  Edite os arquivos 'pt%s' e depois rode: python3 %s"
          % (".msg", os.path.basename(sys.argv[0])))

# --------------------------------------------------------------------------
# Validacoes de uma traducao
# --------------------------------------------------------------------------
def validar_fala(en, pt):
    avisos = []
    if "{" in pt or "}" in pt:
        avisos.append("contem { ou } (quebra o formato .msg)")
    if en is not None:
        if sorted(RE_TOKEN.findall(en)) != sorted(RE_TOKEN.findall(pt)):
            avisos.append("tokens %% diferentes do EN (%s vs %s)"
                          % (sorted(RE_TOKEN.findall(en)), sorted(RE_TOKEN.findall(pt))))
    ruins = []
    for ch in pt:
        try:
            ch.encode("iso-8859-1")
        except UnicodeEncodeError:
            if ch not in ruins:
                ruins.append(ch)
    if ruins:
        det = ", ".join("'%s'(U+%04X)" % (c, ord(c)) for c in ruins)
        avisos.append("fora do ISO-8859-1: %s (troque, ex.: — por -, aspas curvas por retas)" % det)
    return avisos

# --------------------------------------------------------------------------
# SALVAR (default) - varre, gera JSON e atualiza o checkpoint
# --------------------------------------------------------------------------
def _carregar_progresso():
    if not os.path.exists(PROGRESSO):
        print("ERRO: rode 'init' primeiro (progresso.json nao existe)."); sys.exit(1)
    return json.load(open(PROGRESSO, encoding="utf-8"))

def cmd_salvar(args):
    prog = _carregar_progresso()
    alteracoes = []
    novos = editados = revertidos = com_aviso = 0
    parou_em = prog.get("parou_em")

    for chave, info in sorted(prog["arquivos"].items()):
        pt_path = os.path.join(RAIZ, info["pt_rel"])
        en_path = os.path.join(RAIZ, info["en_rel"])
        if not os.path.exists(pt_path):
            continue
        tipo = info["tipo"]
        pt_atual = {it["id"]: it for it in parse(ler_txt(pt_path), tipo)}
        en_atual = {it["id"]: it["texto"] for it in parse(ler_txt(en_path), tipo)}

        houve_mudanca_aqui = False
        for _id, it in pt_atual.items():
            pt_txt = it["texto"]
            en_txt = en_atual.get(_id)                 # None se for extra
            reg = info["ids"].get(_id) or info["ids"].get("EX:" + _id) or {}
            pt_antigo = reg.get("pt")

            if pt_txt == pt_antigo:
                continue                               # nada mudou nesta fala

            st_novo = status_fala(en_txt, pt_txt)
            st_antigo = reg.get("status")
            avisos = validar_fala(en_txt, pt_txt) if st_novo == "traduzido" else []

            if st_antigo == "pendente" and st_novo == "traduzido":
                tipo_mud = "novo"; novos += 1
            elif st_novo == "pendente":
                tipo_mud = "revertido_para_ingles"; revertidos += 1
            else:
                tipo_mud = "editado"; editados += 1
            if avisos:
                com_aviso += 1

            alteracoes.append({
                "arquivo": chave,
                "origem_jogo": info["origem"],
                "id": _id,
                "tipo": tipo_mud,
                "en": en_txt,
                "de": pt_antigo,
                "para": pt_txt,
                "avisos": avisos,
            })
            houve_mudanca_aqui = True

            # atualiza o checkpoint desta fala
            k = _id if _id in info["ids"] else ("EX:" + _id if ("EX:" + _id) in info["ids"] else _id)
            if k not in info["ids"]:
                info["ids"][k] = {"en": en_txt, "audio": it.get("audio", "")}
            info["ids"][k]["pt"] = pt_txt
            info["ids"][k]["status"] = st_novo

        if houve_mudanca_aqui:
            parou_em = chave

    saida = {
        "rodado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resumo": {
            "novas_traducoes": novos,
            "edicoes": editados,
            "voltaram_para_ingles": revertidos,
            "com_aviso": com_aviso,
            "total": len(alteracoes),
        },
        "alteracoes": alteracoes,
    }
    escrever(ALTERACOES, json.dumps(saida, ensure_ascii=False, indent=1))

    prog["parou_em"] = parou_em
    prog["ultima_rodada"] = saida["rodado_em"]
    escrever(PROGRESSO, json.dumps(prog, ensure_ascii=False, indent=1))

    print("Rodado. JSON das alteracoes -> %s" % ALTERACOES)
    print("  novas traducoes      : %d" % novos)
    print("  edicoes              : %d" % editados)
    print("  voltaram p/ ingles   : %d" % revertidos)
    print("  com avisos           : %d" % com_aviso)
    if com_aviso:
        print("  ATENCAO: ha falas com aviso; veja os detalhes no JSON.")
    if parou_em:
        print("  checkpoint salvo. Voce parou em: %s" % parou_em)
    print("\n  Para retomar depois:  python3 %s continuar" % os.path.basename(sys.argv[0]))

# --------------------------------------------------------------------------
# STATUS
# --------------------------------------------------------------------------
def _varrer_status(prog):
    por_cat = {}
    tot = {"traduzido": 0, "pendente": 0, "vazio": 0, "extra": 0}
    for chave, info in prog["arquivos"].items():
        cat = chave.split("/")[0]
        d = por_cat.setdefault(cat, {"traduzido": 0, "pendente": 0, "vazio": 0, "extra": 0})
        pt_path = os.path.join(RAIZ, info["pt_rel"])
        en_path = os.path.join(RAIZ, info["en_rel"])
        if not (os.path.exists(pt_path) and os.path.exists(en_path)):
            continue
        tipo = info["tipo"]
        en_atual = {it["id"]: it["texto"] for it in parse(ler_txt(en_path), tipo)}
        for it in parse(ler_txt(pt_path), tipo):
            st = status_fala(en_atual.get(it["id"]), it["texto"])
            d[st] += 1; tot[st] += 1
    return por_cat, tot

def cmd_status(args):
    prog = _carregar_progresso()
    por_cat, tot = _varrer_status(prog)
    print("PROGRESSO DA TRADUCAO")
    print("-" * 62)
    print("%-10s %10s %10s %8s %7s %7s" % ("categoria", "traduzido", "pendente", "vazio", "extra", "%"))
    for cat in sorted(por_cat):
        d = por_cat[cat]
        base = d["traduzido"] + d["pendente"]
        pct = 100.0 * d["traduzido"] / base if base else 100.0
        print("%-10s %10d %10d %8d %7d %6.1f%%" % (cat, d["traduzido"], d["pendente"], d["vazio"], d["extra"], pct))
    print("-" * 62)
    base = tot["traduzido"] + tot["pendente"]
    pct = 100.0 * tot["traduzido"] / base if base else 100.0
    print("%-10s %10d %10d %8d %7d %6.1f%%" % ("TOTAL", tot["traduzido"], tot["pendente"], tot["vazio"], tot["extra"], pct))
    print("\n(pendente = fala ainda igual ao ingles; vazio = {id}{}{} sem texto no jogo)")

# --------------------------------------------------------------------------
# CONTINUAR - de onde retomar
# --------------------------------------------------------------------------
def cmd_continuar(args):
    prog = _carregar_progresso()
    parou = prog.get("parou_em")
    if parou:
        print("Voce parou por ultimo em: %s\n" % parou)

    # lista arquivos com pendencias, contando ao vivo
    pend_por_arq = []
    for chave, info in sorted(prog["arquivos"].items()):
        pt_path = os.path.join(RAIZ, info["pt_rel"])
        en_path = os.path.join(RAIZ, info["en_rel"])
        if not (os.path.exists(pt_path) and os.path.exists(en_path)):
            continue
        tipo = info["tipo"]
        en_atual = {it["id"]: it["texto"] for it in parse(ler_txt(en_path), tipo)}
        pend_ids = [it for it in parse(ler_txt(pt_path), tipo)
                    if status_fala(en_atual.get(it["id"]), it["texto"]) == "pendente"]
        if pend_ids:
            pend_por_arq.append((chave, info, pend_ids))

    if not pend_por_arq:
        print("Tudo traduzido! Nada pendente. :)")
        return

    print("Arquivos que ainda tem falas em ingles (%d no total):\n" % len(pend_por_arq))
    for chave, info, pend in pend_por_arq[:args.n]:
        print("  %-22s  %4d pendentes   ->  %s" % (chave, len(pend), info["pt_rel"]))
    if len(pend_por_arq) > args.n:
        print("  ... e mais %d arquivos." % (len(pend_por_arq) - args.n))

    # mostra as proximas falas concretas do primeiro arquivo pendente
    chave, info, pend = pend_por_arq[0]
    print("\nProximas falas a traduzir em '%s' (%s):" % (chave, info["pt_rel"]))
    for it in pend[:args.falas]:
        txt = it["texto"].replace("\n", " ").strip()
        print("  [%s] %s" % (it["id"], (txt[:70] + "...") if len(txt) > 70 else txt))

# --------------------------------------------------------------------------
# COMPILAR - gera os .msg finais do jogo (ISO-8859-1)
# --------------------------------------------------------------------------
def _quebra_de_linha(origem, tipo):
    """
    Igual a traducao tcheca:
      * .msg (dialog/game)  -> LF  (\\n)
      * cuts .txt/.TXT      -> CRLF (\\r\\n)
    O jogo (Fallout CE/sfall) le os cuts com CRLF; os .msg com LF.
    """
    if tipo == "numerado" or origem.lower().endswith((".txt",)):
        return "\r\n"
    return "\n"

def _normalizar_quebras(texto, nl):
    """Zera qualquer \\r\\n / \\r solto e reaplica a quebra desejada."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    if nl != "\n":
        texto = texto.replace("\n", nl)
    return texto

def cmd_compilar(args):
    prog = _carregar_progresso()
    # raiz de saida: traducao/saida_jogo/<mod>/text/<lang>/
    base_saida = os.path.join(DIR_JOGO, args.mod, "text", args.lang)
    n = falhas = 0
    problemas = []
    detalhes = []   # (origem, caractere, U+xxxx)
    for chave, info in sorted(prog["arquivos"].items()):
        pt_path = os.path.join(RAIZ, info["pt_rel"])
        if not os.path.exists(pt_path):
            continue
        conteudo = ler_txt(pt_path)              # ja esta em formato de jogo
        nl = _quebra_de_linha(info["origem"], info.get("tipo", "braced"))
        conteudo = _normalizar_quebras(conteudo, nl)

        # destino espelha o caminho original dentro de text/<lang>/
        # normaliza a extensao pra casar com a tcheca:
        #   game/ e dialog/ -> sempre .msg minusculo (a tcheca usa assim)
        #   cuts/           -> preserva a caixa original (.txt/.TXT, igual a tcheca)
        origem = info["origem"]
        raiz_rel = origem.replace("\\", "/").split("/", 1)[0].lower()
        if raiz_rel in ("game", "dialog"):
            base_nome, ext = os.path.splitext(origem)
            if ext.lower() == ".msg":
                origem = base_nome + ".msg"
        dest = os.path.join(base_saida, origem)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            dados = conteudo.encode("iso-8859-1")
        except UnicodeEncodeError:
            falhas += 1
            # aponta exatamente quais caracteres nao cabem no ISO-8859-1
            ruins = []
            for ch in conteudo:
                try:
                    ch.encode("iso-8859-1")
                except UnicodeEncodeError:
                    if ch not in ruins and ch not in ("\r", "\n"):
                        ruins.append(ch)
            problemas.append((info["origem"], ruins))
            dados = conteudo.encode("iso-8859-1", errors="replace")
        with open(dest, "wb") as f:
            f.write(dados)
        n += 1

    print("COMPILAR concluido -> %s/" % base_saida)
    print("  estrutura            : %s/text/%s/{dialog,game,cuts}/" % (args.mod, args.lang))
    print("  arquivos gerados     : %d" % n)
    print("  codificacao          : ISO-8859-1")
    print("  quebras de linha     : .msg = LF | cuts .txt/.TXT = CRLF (igual a tcheca)")
    if falhas:
        print("\n  ATENCAO: %d arquivo(s) com caractere fora do ISO-8859-1 (viraram '?'):" % falhas)
        for origem, ruins in problemas[:12]:
            det = ", ".join("'%s'(U+%04X)" % (c, ord(c)) for c in ruins[:6])
            print("    - %s  ->  %s" % (origem, det))
        print("  Troque esses caracteres (ex.: travessao — por -, aspas curvas \u201c \u201d por \"),")
        print("  rode 'python3 %s' pra ver as falas exatas, e compile de novo." % os.path.basename(sys.argv[0]))
    else:
        print("  Sem caracteres invalidos. Pronto pra jogar.")
    print("\n  Copie a pasta '%s' pra dentro do seu Fallout (mods) e ative a lingua '%s'." % (args.mod, args.lang))

# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Traducao PT-BR do Fallout (com checkpoint)")
    sub = ap.add_subparsers(dest="cmd")

    i = sub.add_parser("init", help="cria a arvore de pastas en/pt a partir dos originais")
    i.add_argument("--en", required=True, help="pasta com os arquivos em INGLES")
    i.add_argument("--pt", required=True, help="pasta com a traducao PT-BR existente")
    i.add_argument("--forcar", action="store_true", help="regera pt.msg mesmo se ja existir (CUIDADO)")
    i.set_defaults(func=cmd_init)

    s = sub.add_parser("salvar", help="varre, gera o JSON e salva o checkpoint")
    s.set_defaults(func=cmd_salvar)

    st = sub.add_parser("status", help="mostra o progresso")
    st.set_defaults(func=cmd_status)

    c = sub.add_parser("continuar", help="mostra de onde retomar")
    c.add_argument("-n", type=int, default=12, help="quantos arquivos listar")
    c.add_argument("--falas", type=int, default=8, help="quantas falas do 1o arquivo mostrar")
    c.set_defaults(func=cmd_continuar)

    cp = sub.add_parser("compilar", help="gera os .msg finais do jogo (ISO-8859-1), na estrutura da tcheca")
    cp.add_argument("--mod",  default=MOD_PADRAO,  help="nome da pasta do mod (padrao: %s)" % MOD_PADRAO)
    cp.add_argument("--lang", default=LANG_PADRAO, help="nome da lingua/subpasta text (padrao: %s)" % LANG_PADRAO)
    cp.set_defaults(func=cmd_compilar)

    args = ap.parse_args()
    if not args.cmd:                      # rodar sem argumento = salvar
        args.func = cmd_salvar
    args.func(args)

if __name__ == "__main__":
    main()
