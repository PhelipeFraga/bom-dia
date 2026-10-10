# Bom dia

Página pessoal para abrir ao acordar: clima de São Paulo (céu animado, próximas 24 horas, 7 dias, radar de chuva) e, nas próximas versões, notícias, foto do dia da NASA, neste dia na história, palavra em inglês, jogos e estreias.

- Funciona como app no celular (PWA): abra o link e use "Adicionar à tela inicial".
- Clima: [Open-Meteo](https://open-meteo.com) · Radar: [RainViewer](https://www.rainviewer.com) · Mapa: CARTO/OpenStreetMap.
- Nada pessoal fica neste repositório: lembretes serão guardados só no aparelho.

Dados: clima e radar são buscados ao vivo pela página; notícias, foto da NASA, "neste dia" e palavra do dia vêm do robô `scripts/coletar.py`, que roda no GitHub Actions todo dia às 6h50 (e pode ser disparado em Actions → "Coletar dados do Bom dia" → Run workflow).
