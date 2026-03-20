# Album Splitter by Jair Lima

Divide um MP3 de CD Completo em faixas individuais usando ffmpeg,
com busca automática de tracklist no MusicBrainz.

## Stack e dependências

- Python 3.11+
- Tkinter (UI nativa, já inclusa no Python)
- ffmpeg / ffprobe (binários externos, não versionados)
- requests (chamadas à API do MusicBrainz)
- tkinterdnd2 (drag and drop, opcional)

Instalar dependências:
```
pip install -r requirements.txt
pip install tkinterdnd2  # opcional, habilita drag and drop
```

## Estrutura

```
AlbumSplitter/
├── app.py          # UI Tkinter: janela principal, busca, edição, progresso
├── splitter.py     # Lógica de corte via ffmpeg; detecção de duração via ffprobe
├── searcher.py     # Busca no MusicBrainz, retorna [(titulo, segundos)]
├── requirements.txt
├── ffmpeg.exe      # não versionado (.gitignore)
└── ffprobe.exe     # não versionado (.gitignore)
```

## Comandos essenciais

```bash
# Rodar o app
python app.py

# Gerar executável standalone (PyInstaller)
pyinstaller AlbumSplitter.spec
```

## Fluxo de split

1. `splitter.split_album` recebe `[(titulo, duracao_segundos), ...]`
2. Calcula `starts[]` acumulando durações
3. Para cada faixa: `ffmpeg -ss <start> -i <input> -t <dur> -acodec copy`
4. Última faixa não usa `-t` (captura até o fim do arquivo)
5. Metadados ID3 gravados via `-metadata` em cada faixa

## Decisões arquiteturais

- **Sem re-encoding:** `-acodec copy` garante corte rápido e sem perda de qualidade.
- **MusicBrainz sem chave:** API pública, rate limit de 1 req/s respeitado com `time.sleep(1.1)`.
- **Última faixa sem `-t`:** evita corte prematuro por imprecisão nas durações da tracklist.
- **tkinterdnd2 opcional:** o app funciona normalmente sem ela; drag and drop é bônus.

## Problemas conhecidos

- **MusicBrainz sem duração:** alguns álbuns não têm `length` nas faixas (retorna 0).
  O app detecta, marca em vermelho e pede confirmação antes de dividir.
- **Sem histórico git:** o projeto foi desenvolvido sem commits intermediários.
  O repositório tem apenas o commit inicial com todos os arquivos.

## Estado atual

Funcional. Publicado em: https://github.com/jairslima/album-splitter

Última sessão (2026-03-20):
- Adicionado label "Album Splitter by Jair Lima" visível no topo da UI (verde, negrito)
- Regra global de autoria atualizada: o nome deve aparecer na UI, não só na barra de título

## Próximos passos possíveis

- Suporte a múltiplos discos (CD1/CD2)
- Busca alternativa quando MusicBrainz não encontra (ex: Discogs)
- Exportar/importar tracklist em formato texto

---

## Boas práticas para projetos futuros

**Iniciar git desde o primeiro arquivo:**

```bash
git init
git add .
git commit -m "Initial commit"
```

Fazer commits ao longo do desenvolvimento, um por funcionalidade ou sessão.
Isso cria um histórico real que documenta a evolução do projeto e facilita
reverter mudanças se algo quebrar.
