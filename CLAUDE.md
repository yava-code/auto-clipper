# ClipQueue — Claude Code Instructions

## Правило №1
Перед любым действием прочитай `PRD.md` полностью. Это единственный источник истины.
Если что-то не описано в PRD — спроси, не придумывай.

## Как работать

Ты работаешь строго по фазам из PRD раздела 10.
- Одна сессия = одна задача из чеклиста текущей фазы
- После завершения задачи — стоп. Отчёт что сделано, что следующее
- Не переходи к следующей фазе пока все пункты текущей не закрыты
- Каждый завершённый пункт — коммит с осмысленным сообщением

## Суб-агенты — когда вызывать

Установи из `github.com/VoltAgent/awesome-claude-code-subagents`:

```
claude code --add-agent python-expert
claude code --add-agent ui-designer  
claude code --add-agent code-quality-guardian
claude code --add-agent project-setup-wizard
```

| Задача | Вызови агента |
|--------|---------------|
| Структура проекта, requirements.txt | `@project-setup-wizard` |
| core/queue.py, core/parser.py | `@python-expert` |
| ui/window.py, layout, цвета | `@ui-designer` |
| WinAPI, UAC, хоткей конфликты | `@windows-automation-specialist` |
| Перед коммитом каждой фазы | `@code-quality-guardian` |
| Race condition, sleep тюнинг | `@performance-profiler` |

## Скиллы — читай перед написанием кода

Доступные скиллы в `.claude/skills/`:
- Если создаёшь UI компонент → прочитай `frontend-design/SKILL.md`
- Если создаёшь документацию → прочитай `docx/SKILL.md`

Если скилл нужен но не установлен — сообщи какой и зачем.

## Стиль кода (обязательно)

- Короткие имена переменных: `idx`, `res`, `q`, `buf`
- Комментарии только про *почему*, никогда про *что*
- Не обрабатывай каждый edge case — только то что нужно сейчас
- Без type hints везде подряд
- Без секций типа `# === SECTION ===`
- Меньше кода лучше чем больше

## Структура файлов (из PRD)

```
clipqueue/
├── main.py
├── core/
│   ├── queue.py
│   └── parser.py
├── ui/
│   └── window.py
├── config.json
├── requirements.txt
├── build.spec
└── README.md
```

Не создавай файлы вне этой структуры без явного запроса.

## Definition of Done для каждой задачи

Прежде чем сказать "готово":
- [ ] Протестировано в Notepad
- [ ] Протестировано в Excel  
- [ ] Протестировано в Chrome (поле ввода)
- [ ] `@code-quality-guardian` прогнан
- [ ] Коммит сделан

## Формат отчёта после задачи

```
✅ Сделано: [что именно]
📁 Файлы: [какие созданы/изменены]
🧪 Тесты: [результат в 3 приложениях]
⏭️ Следующее: [следующий пункт чеклиста из PRD]
⚠️ Риски: [если есть]
```
