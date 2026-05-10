# LikeC4 on GitHub Pages

Статический LikeC4-site публикуется в GitHub Pages через GitHub Actions workflow
[`deploy-likec4-pages.yml`](../../.github/workflows/deploy-likec4-pages.yml).

## Источник публикации

- Pages source: custom GitHub Actions workflow
- deploy branch: `main`
- base path для LikeC4 build: `/industrial-data-platform/`
- build output: `arch/dist`

## Публичный URL

Для текущего репозитория `SergeyDubovitsky/industrial-data-platform` ожидаемый URL:
[https://sergeydubovitsky.github.io/industrial-data-platform/](https://sergeydubovitsky.github.io/industrial-data-platform/).

## Локальная проверка

Из директории [`arch`](../../arch):

```bash
npm run validate
npm run build -- --base /industrial-data-platform/
```

Команда `build -- --base /industrial-data-platform/` воспроизводит project-site
base path, который GitHub Pages использует для репозитория
`industrial-data-platform`.

## Обновление публикации

Workflow публикует сайт автоматически при push в `main`, если изменилось
что-то внутри `arch/`, а также поддерживает ручной запуск через
`workflow_dispatch`.

Внутри workflow:

1. `actions/configure-pages@v5` получает правильный `base_path`
2. `likec4/actions@v1` собирает static site из [`arch`](../../arch)
3. `actions/upload-pages-artifact@v4` загружает `arch/dist`
4. `actions/deploy-pages@v4` публикует артефакт в environment `github-pages`
