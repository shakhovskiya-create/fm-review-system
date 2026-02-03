using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;
using DocumentFormat.OpenXml;

if (args.Length == 0) { Console.WriteLine("Usage: dotnet run <file.docx>"); return; }

var docPath = args[0];
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine();

// Бэкап
var backup = docPath.Replace(".docx", $"_{DateTime.Now:HHmmss}.bak");
System.IO.File.Copy(docPath, backup, true);
Console.WriteLine($"💾 Бэкап: {System.IO.Path.GetFileName(backup)}");
Console.WriteLine();

var doc = WordprocessingDocument.Open(docPath, true);
var body = doc.MainDocumentPart!.Document.Body!;

var author = "Шаховский А.С.";
var date = DateTime.Parse("2026-01-29");
int id = 200000;
int fixes = 0;

Console.WriteLine("🔧 ИСПРАВЛЕНИЯ:");
Console.WriteLine();

// 1. Обновить версию в ТАБЛИЦЕ 1 (паспорт)
var tables = body.Elements<Table>().ToList();
if (tables.Count > 0)
{
    var table1 = tables[0];
    var rows = table1.Elements<TableRow>().ToList();
    if (rows.Count > 0)
    {
        var versionRow = rows[0];
        var cells = versionRow.Elements<TableCell>().ToList();
        if (cells.Count >= 2)
        {
            var versionCell = cells[1];
            var para = versionCell.Elements<Paragraph>().FirstOrDefault();
            if (para != null)
            {
                // Удалить старый текст
                var oldRun = para.Elements<Run>().FirstOrDefault();
                if (oldRun != null && oldRun.InnerText.Contains("1.2.0"))
                {
                    var delRun = new DeletedRun { Author = author, Date = date, Id = (id++).ToString() };
                    delRun.AppendChild(new DeletedText("1.2.0"));
                    para.InsertBefore(delRun, oldRun);
                    oldRun.Remove();

                    // Вставить новый текст
                    var insRun = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
                    insRun.AppendChild(new Run(new Text("1.2.1")));
                    para.AppendChild(insRun);

                    Console.WriteLine("  ✅ ТАБЛИЦА 1: Версия 1.2.0 → 1.2.1");
                    fixes++;
                }
            }
        }
    }
}

// 2. Добавить строку в ТАБЛИЦУ 2 (история версий)
if (tables.Count > 1)
{
    var table2 = tables[1];
    var newRow = new TableRow();

    // Версия
    var cell1 = new TableCell();
    var ins1 = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
    ins1.AppendChild(new Run(new Text("1.2.1")));
    cell1.Append(new Paragraph(ins1));
    newRow.Append(cell1);

    // Дата
    var cell2 = new TableCell();
    var ins2 = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
    ins2.AppendChild(new Run(new Text("29.01.2026")));
    cell2.Append(new Paragraph(ins2));
    newRow.Append(cell2);

    // Автор
    var cell3 = new TableCell();
    var ins3 = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
    ins3.AppendChild(new Run(new Text("Шаховский А.С.")));
    cell3.Append(new Paragraph(ins3));
    newRow.Append(cell3);

    // Описание
    var cell4 = new TableCell();
    var ins4 = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
    ins4.AppendChild(new Run(new Text("Интеграция 31 исправления из аудита логики: CRITICAL (4), HIGH (13), MEDIUM (10), LOW (4). Основные изменения: защита от конфликта параллельных операций, уточнение формул, правила округления, разделение возвратов по причинам.")));
    cell4.Append(new Paragraph(ins4));
    newRow.Append(cell4);

    table2.Append(newRow);
    Console.WriteLine("  ✅ ТАБЛИЦА 2: Добавлена строка v1.2.1");
    fixes++;
}

// 3. Заменить "race condition" → "конфликт параллельных операций"
int raceConditionFixed = 0;
foreach (var para in body.Descendants<Paragraph>())
{
    var text = para.InnerText;
    if (text.Contains("race condition"))
    {
        foreach (var run in para.Elements<Run>().ToList())
        {
            foreach (var textElem in run.Elements<Text>().ToList())
            {
                if (textElem.Text.Contains("race condition"))
                {
                    // Удалить старый текст
                    var delRun = new DeletedRun { Author = author, Date = date, Id = (id++).ToString() };
                    delRun.AppendChild(new DeletedText(textElem.Text));
                    para.InsertBefore(delRun, run);

                    // Вставить новый текст
                    var newText = textElem.Text.Replace("race condition", "конфликт параллельных операций");
                    var insRun = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
                    insRun.AppendChild(new Run(new Text(newText) { Space = SpaceProcessingModeValues.Preserve }));
                    para.InsertBefore(insRun, run);

                    run.Remove();
                    raceConditionFixed++;
                    break;
                }
            }
        }
    }
}
Console.WriteLine($"  ✅ Замена 'race condition': {raceConditionFixed} вхождений");
fixes += raceConditionFixed;

// 4. Удалить длинный технический текст про версию 1.2.0
int techTextRemoved = 0;
foreach (var para in body.Descendants<Paragraph>().ToList())
{
    var text = para.InnerText;
    if (text.Contains("Интеграция 22 логических исправлений из аудита Logic Review"))
    {
        // Удалить весь параграф как tracked change
        var delPara = new DeletedRun { Author = author, Date = date, Id = (id++).ToString() };
        delPara.AppendChild(new DeletedText(text));

        para.RemoveAllChildren();
        para.AppendChild(delPara);

        techTextRemoved++;
        Console.WriteLine($"  ✅ Удален технический текст про v1.2.0 (параграф)");
        fixes++;
    }
}

doc.MainDocumentPart.Document.Save();
doc.Dispose();

Console.WriteLine();
Console.WriteLine(new string('=', 60));
Console.WriteLine($"✅ {fixes} исправлений применено");
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine($"💾 {System.IO.Path.GetFileName(backup)}");
Console.WriteLine(new string('=', 60));
