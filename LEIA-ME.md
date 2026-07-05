# Tradução PT-BR do Fallout — fluxo com checkpoint

**Cada arquivo tem a sua pasta**, com o inglês e o português **sempre lá e
separados**. O que ainda não foi traduzido fica **em inglês** dentro do `pt`,
então você nunca fica sem o texto de origem. Você edita, **roda o `.py`**, ele
gera um **JSON do que mudou** e **salva o ponto onde você parou** — na próxima
vez você continua de onde estava.

## Estrutura

```
traduzir.py
traducao/
├── arquivos/
│   ├── dialog/
│   │   ├── ABEL/
│   │   │   ├── en.msg   <- INGLÊS (referência — não edite)
│   │   │   └── pt.msg   <- TRADUÇÃO (edite aqui)
│   │   ├── BAKA/
│   │   │   ├── en.msg
│   │   │   └── pt.msg
│   │   └── ...
│   ├── game/...
│   └── cuts/...   (aqui os arquivos são en.txt / pt.txt)
├── progresso.json   <- o checkpoint (onde você parou). Não edite à mão.
└── alteracoes.json  <- gerado quando você roda o .py
```

Regra que o programa usa: **no `pt.msg`, uma fala idêntica ao inglês = ainda
pendente.** Assim que você troca o texto, ela passa a contar como traduzida.
Nada de marcador estranho — você traduz "por cima" do inglês.

Estado atual: **~75,6% traduzido** (31.774 falas prontas, 10.270 ainda em inglês).

## O dia a dia

1. Abra o `pt.msg` da pasta que quer traduzir (ex.:
   `traducao/arquivos/dialog/BAKA/pt.msg`). Se quiser ver o original ao lado,
   abra o `en.msg` da mesma pasta.
2. Traduza as falas (troque o texto inglês pelo português). Salve.
3. Rode o programa:

   ```
   python3 traduzir.py
   ```

   Isso:
   - gera **`traducao/alteracoes.json`** com exatamente o que você mudou;
   - **salva o checkpoint** (o ponto onde você parou).

   Exemplo de uma entrada do JSON:

   ```json
   {
     "arquivo": "dialog/BAKA",
     "origem_jogo": "dialog/BAKA.msg",
     "id": "100",
     "tipo": "novo",
     "en": "You see: Baka.",
     "de": "You see: Baka.",
     "para": "Você vê: Baka.",
     "avisos": []
   }
   ```

   `tipo` pode ser `novo` (estava em inglês, agora traduzido), `editado`
   (mudou um já traduzido) ou `revertido_para_ingles`.

4. Quando voltar depois, veja de onde retomar:

   ```
   python3 traduzir.py continuar
   ```

   Ele mostra onde você parou e lista os próximos arquivos e falas ainda em
   inglês.

## Comandos

| Comando | O que faz |
|---|---|
| `python3 traduzir.py` | (sem argumento) varre tudo, gera o JSON e salva o checkpoint |
| `python3 traduzir.py continuar` | mostra de onde retomar |
| `python3 traduzir.py status` | tabela de progresso por categoria |
| `python3 traduzir.py compilar` | gera os `.msg` finais do jogo em `traducao/saida_jogo/` (ISO-8859-1) |
| `python3 traduzir.py init --en ... --pt ...` | recria a árvore do zero (não sobrescreve `pt` já editado, a menos que use `--forcar`) |

## As validações (rodam a cada `traduzir.py`)

Toda fala alterada é checada contra os 3 problemas clássicos desse jogo:

1. **Tokens `%s %d`** — se o inglês tem `%d` e sua tradução não, o jogo dá erro.
   Acusado.
2. **Chaves `{ }`** no texto — quebram o formato `.msg`. Acusado.
3. **Codificação ISO-8859-1** — o Fallout não aceita travessão (`—`), aspas
   curvas (`" "`) nem emoji. O programa aponta o caractere exato e sugere a
   troca. (Você edita em UTF-8; a conversão pra ISO-8859-1 acontece só no
   `compilar`.)

Falas com problema aparecem no JSON com o campo `avisos` preenchido.

## Observações

- Cobre `dialog`, `game` e `cuts` do módulo principal (`fo1_lang_brazilian`),
  ~44 mil falas. Módulos extras e arquivos `.bio`/`.sve` ficam de fora desta
  versão (veja a branch `modulos_extra_ptbr`).
- **Falas "extra" (397)**: existem só na sua tradução (de outra versão), não no
  inglês atual. Foram preservadas no fim do `pt.msg` pra não perder trabalho.
- **Falas "vazio" (1.514)**: são `{id}{}{}` sem texto no próprio jogo. Não
  precisam de tradução e não entram na conta de pendências.
- Uma fala traduzida que ficar idêntica ao inglês (ex.: nomes próprios, "OK")
  vai aparecer como "pendente". Se for proposital, é só ignorar.
