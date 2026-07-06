# Tradução PT-BR do Fallout (1997)

Tradução da comunidade do Fallout original (1997) para português do Brasil.
Roda tanto no jogo original quanto no Fallout Community Edition (fo1-ce) /
sfall.

Estado atual: **~95% traduzido** (39.561 falas prontas). As ~2.483 falas
restantes que aparecem como pendentes **não precisam de tradução** — são
nomes próprios, onomatopeias e afins (ex.: "Pik! Pik!") que ficam iguais em
português.

## O que tem aqui

Esta branch (`main`) já traz os dois pacotes prontos pra copiar pra pasta do
jogo:

| Pasta | O que é | Necessário? |
|---|---|---|
| [`fo1_lang_brazilian/`](fo1_lang_brazilian) | Tradução principal: `dialog`, `game` e `cuts` (~44 mil falas) | Sim |
| [`modulos_extra_ptbr/`](modulos_extra_ptbr) | Módulos extras: Appearance, finais alternativos de Junktown, premades, Robodog, `Translations.ini` do sfall | Opcional |

Se você só quer um dos dois isolado (sem a outra pasta junto), cada um também
tem sua própria branch: [`fo1_lang_brazilian`](../../tree/fo1_lang_brazilian)
e [`modulos_extra_ptbr`](../../tree/modulos_extra_ptbr).

## Como instalar

1. Copie a pasta `fo1_lang_brazilian` pra dentro da pasta `mods` do seu
   Fallout.
2. (Opcional) Copie as subpastas de `modulos_extra_ptbr` junto — veja o
   `LEIA-ME_modulos.txt` dentro pra detalhes de cada módulo.
3. No arquivo `fallout2.cfg`, confira se o idioma está configurado como
   `language=brazilian`.
4. Abra o arquivo `mods_order.txt`, na pasta `mods`, e remova o ponto e
   vírgula antes de `fo1_lang_brazilian`.

O jogo carrega os mods na ordem em que estão listados no `mods_order.txt`.

## Quer contribuir com a tradução?

O fluxo de tradução (com checkpoint, validações e o script `traduzir.py`)
vive na branch [`dev`](../../tree/dev) — o `LEIA-ME.md` de lá explica o
dia a dia de como traduzir uma fala e gerar os arquivos finais do jogo.
