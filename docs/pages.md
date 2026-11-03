# Публикация демо через GitHub Pages

Источник сайта — только `site/`: главная страница index.html и существующий автономный pilot-dragon.html. Основной README остаётся документацией репозитория. CSV/миры/локальные отчёты в artifact не входят.

Workflow `.github/workflows/pages.yml` использует официальные actions: checkout v6, configure-pages v5, upload-pages-artifact v4 и deploy-pages v4. Build имеет contents:read; deploy — pages:write и id-token:write, environment github-pages. Группа concurrency pages предотвращает одновременные deployment; выполняющийся deployment не отменяется новым push. Секреты не нужны. Источник версий: [официальная документация GitHub](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

После проверки PR:

1. В FunGluck/TickSense откройте **Settings → Pages → Build and deployment → Source** и выберите **GitHub Actions** вместо Deploy from a branch. При необходимости нужны права администратора репозитория.
2. Объедините PR в main. Агент не выполняет автоматический merge.
3. В Actions дождитесь успешного **Deploy TickSense demo to Pages**. При необходимости запустите его вручную через Run workflow на main. До merge feature-ветка автоматически не публикуется.
4. Проверьте адреса https://fungluck.github.io/TickSense/ и https://fungluck.github.io/TickSense/pilot-dragon.html. Нажмите «Посмотреть пример отчёта», проверьте графики, выбор сессии, масштабирование и мобильную ширину. Успешный push/PR сам по себе не доказывает публикацию.

В локальной проверке: HTML/JSON прочитаны, внешние загружаемые ресурсы и локальные абсолютные пути в демо не найдены, встроенный JS проходит node --check, тесты навигации проходят без браузера. Демо сохранено из origin/main без изменения содержимого; различие CRLF/LF рабочей копии учитывается Git.

Попытка визуально открыть локальный file:// заблокирована политикой браузерного инструмента; обход не выполнялся. Поэтому визуальная проверка в настоящем браузере остаётся ручным действием. Факт успешной публикации будет установлен только после успешного deployment и проверки обеих страниц.
