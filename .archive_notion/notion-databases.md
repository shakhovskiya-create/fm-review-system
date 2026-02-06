# 📊 Notion Database Schemas

Схемы для создания баз данных в Notion через API/MCP.

---

## 1. Функциональные модели (FM)

```json
{
  "database_id": "fm_database",
  "title": "📄 Функциональные модели",
  "properties": {
    "Код": {
      "type": "title",
      "title": {}
    },
    "Название": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Версия": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Статус": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Draft", "color": "gray" },
          { "name": "Review", "color": "yellow" },
          { "name": "Approved", "color": "green" },
          { "name": "Archived", "color": "brown" }
        ]
      }
    },
    "Приоритет": {
      "type": "select",
      "select": {
        "options": [
          { "name": "P0", "color": "red" },
          { "name": "P1", "color": "orange" },
          { "name": "P2", "color": "yellow" },
          { "name": "P3", "color": "gray" }
        ]
      }
    },
    "Автор": {
      "type": "people",
      "people": {}
    },
    "Владелец процесса": {
      "type": "people",
      "people": {}
    },
    "Область": {
      "type": "multi_select",
      "multi_select": {
        "options": [
          { "name": "Продажи", "color": "blue" },
          { "name": "Логистика", "color": "green" },
          { "name": "Финансы", "color": "purple" },
          { "name": "IT", "color": "gray" },
          { "name": "Закупки", "color": "orange" }
        ]
      }
    },
    "Системы": {
      "type": "multi_select",
      "multi_select": {
        "options": [
          { "name": "1С:УТ", "color": "yellow" },
          { "name": "1С:ДО", "color": "orange" },
          { "name": "1С:ERP", "color": "red" },
          { "name": "WMS", "color": "green" },
          { "name": "CRM", "color": "blue" },
          { "name": "BI", "color": "purple" }
        ]
      }
    },
    "Miro Board": {
      "type": "url",
      "url": {}
    },
    "Требования": {
      "type": "relation",
      "relation": {
        "database_id": "requirements_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "ФМ"
        }
      }
    },
    "Глоссарий": {
      "type": "relation",
      "relation": {
        "database_id": "glossary_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "ФМ"
        }
      }
    },
    "Риски": {
      "type": "relation",
      "relation": {
        "database_id": "risks_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "ФМ"
        }
      }
    },
    "Зависимости": {
      "type": "relation",
      "relation": {
        "database_id": "fm_database",
        "type": "single_property"
      }
    },
    "Дата создания": {
      "type": "created_time",
      "created_time": {}
    },
    "Дата обновления": {
      "type": "last_edited_time",
      "last_edited_time": {}
    }
  }
}
```

---

## 2. Требования (Requirements)

```json
{
  "database_id": "requirements_database",
  "title": "📋 Требования",
  "properties": {
    "Код": {
      "type": "title",
      "title": {}
    },
    "Название": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Тип": {
      "type": "select",
      "select": {
        "options": [
          { "name": "BR", "color": "blue" },
          { "name": "FR", "color": "green" },
          { "name": "WF", "color": "yellow" },
          { "name": "RPT", "color": "purple" },
          { "name": "NFR", "color": "gray" },
          { "name": "INT", "color": "orange" },
          { "name": "SEC", "color": "red" }
        ]
      }
    },
    "Приоритет": {
      "type": "select",
      "select": {
        "options": [
          { "name": "P1 (MVP)", "color": "red" },
          { "name": "P2 (Phase 2)", "color": "yellow" },
          { "name": "P3 (Backlog)", "color": "gray" }
        ]
      }
    },
    "Статус": {
      "type": "select",
      "select": {
        "options": [
          { "name": "New", "color": "gray" },
          { "name": "InProgress", "color": "blue" },
          { "name": "Done", "color": "green" },
          { "name": "Blocked", "color": "red" },
          { "name": "Cancelled", "color": "brown" }
        ]
      }
    },
    "Сложность": {
      "type": "select",
      "select": {
        "options": [
          { "name": "XS", "color": "gray" },
          { "name": "S", "color": "green" },
          { "name": "M", "color": "yellow" },
          { "name": "L", "color": "orange" },
          { "name": "XL", "color": "red" }
        ]
      }
    },
    "ФМ": {
      "type": "relation",
      "relation": {
        "database_id": "fm_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "Требования"
        }
      }
    },
    "Зависит от": {
      "type": "relation",
      "relation": {
        "database_id": "requirements_database",
        "type": "single_property"
      }
    },
    "Блокирует": {
      "type": "relation",
      "relation": {
        "database_id": "requirements_database",
        "type": "single_property"
      }
    },
    "Автор": {
      "type": "people",
      "people": {}
    },
    "Исполнитель": {
      "type": "people",
      "people": {}
    },
    "Deadline": {
      "type": "date",
      "date": {}
    },
    "Создано": {
      "type": "created_time",
      "created_time": {}
    },
    "Обновлено": {
      "type": "last_edited_time",
      "last_edited_time": {}
    }
  }
}
```

---

## 3. Глоссарий (Glossary)

```json
{
  "database_id": "glossary_database",
  "title": "📖 Глоссарий",
  "properties": {
    "Термин": {
      "type": "title",
      "title": {}
    },
    "Определение": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Аббревиатура": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Синонимы": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Категория": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Бизнес", "color": "blue" },
          { "name": "Технический", "color": "gray" },
          { "name": "Юридический", "color": "purple" },
          { "name": "Финансовый", "color": "green" }
        ]
      }
    },
    "ФМ": {
      "type": "relation",
      "relation": {
        "database_id": "fm_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "Глоссарий"
        }
      }
    },
    "Создано": {
      "type": "created_time",
      "created_time": {}
    }
  }
}
```

---

## 4. Риски (Risks)

```json
{
  "database_id": "risks_database",
  "title": "⚠️ Риски",
  "properties": {
    "Название": {
      "type": "title",
      "title": {}
    },
    "Описание": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Категория": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Технический", "color": "gray" },
          { "name": "Организационный", "color": "yellow" },
          { "name": "Внешний", "color": "blue" }
        ]
      }
    },
    "Вероятность": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Низкая", "color": "green" },
          { "name": "Средняя", "color": "yellow" },
          { "name": "Высокая", "color": "red" }
        ]
      }
    },
    "Влияние": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Низкое", "color": "green" },
          { "name": "Среднее", "color": "yellow" },
          { "name": "Высокое", "color": "orange" },
          { "name": "Критическое", "color": "red" }
        ]
      }
    },
    "Статус": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Открыт", "color": "red" },
          { "name": "Митигирован", "color": "yellow" },
          { "name": "Закрыт", "color": "green" },
          { "name": "Принят", "color": "gray" }
        ]
      }
    },
    "Митигация": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Владелец": {
      "type": "people",
      "people": {}
    },
    "ФМ": {
      "type": "relation",
      "relation": {
        "database_id": "fm_database",
        "type": "dual_property",
        "dual_property": {
          "synced_property_name": "Риски"
        }
      }
    },
    "Создано": {
      "type": "created_time",
      "created_time": {}
    },
    "Обновлено": {
      "type": "last_edited_time",
      "last_edited_time": {}
    }
  }
}
```

---

## 5. История версий (Version History)

```json
{
  "database_id": "versions_database",
  "title": "📝 История версий",
  "properties": {
    "Версия": {
      "type": "title",
      "title": {}
    },
    "ФМ": {
      "type": "relation",
      "relation": {
        "database_id": "fm_database",
        "type": "single_property"
      }
    },
    "Дата": {
      "type": "date",
      "date": {}
    },
    "Автор": {
      "type": "people",
      "people": {}
    },
    "Изменения": {
      "type": "rich_text",
      "rich_text": {}
    },
    "Тип": {
      "type": "select",
      "select": {
        "options": [
          { "name": "Major", "color": "red" },
          { "name": "Minor", "color": "yellow" },
          { "name": "Patch", "color": "gray" }
        ]
      }
    }
  }
}
```

---

## Создание баз через Notion API

```javascript
// Создать все базы данных
async function setupNotionWorkspace(parentPageId) {
  const databases = [
    { schema: fmDatabaseSchema, name: "fm_database" },
    { schema: requirementsSchema, name: "requirements_database" },
    { schema: glossarySchema, name: "glossary_database" },
    { schema: risksSchema, name: "risks_database" },
    { schema: versionsSchema, name: "versions_database" }
  ];
  
  const dbIds = {};
  
  for (const db of databases) {
    const response = await notion.databases.create({
      parent: { page_id: parentPageId },
      title: [{ text: { content: db.schema.title } }],
      properties: db.schema.properties
    });
    dbIds[db.name] = response.id;
  }
  
  // Обновить relations с реальными ID
  // ...
  
  return dbIds;
}
```
