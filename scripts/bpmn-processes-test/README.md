# Тестовые BPMN-примеры

Папка для примеров и экспериментов с BPMN. Исходные процессы в `bpmn-processes/` и вывод в `output/` не трогаем.

Генерация drawio — результат в эту же папку, в `output/`:

```bash
# из корня scripts/
node generate-bpmn.js bpmn-processes-test/order-lifecycle-example.json bpmn-processes-test/output --no-open
```

Результат: `bpmn-processes-test/output/order-lifecycle-example.drawio` и `order-lifecycle-example.png`.
