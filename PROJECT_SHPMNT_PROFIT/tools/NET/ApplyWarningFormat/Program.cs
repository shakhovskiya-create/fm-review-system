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
int id = 300000;
int count = 0;

Console.WriteLine("⛔ ПРИМЕНЕНИЕ ФОРМАТИРОВАНИЯ:");
Console.WriteLine();

// Найти все параграфы с ⚠️ (но БЕЗ "КРИТИЧЕСКАЯ")
foreach (var para in body.Descendants<Paragraph>().ToList())
{
    var text = para.InnerText;
    if (text.Contains("⚠️") && !text.Contains("КРИТИЧЕСКАЯ"))
    {
        // Найти run с ⚠️ и заменить
        foreach (var run in para.Elements<Run>().ToList())
        {
            foreach (var textElem in run.Elements<Text>().ToList())
            {
                if (textElem.Text.Contains("⚠️"))
                {
                    // Удалить старый текст
                    var delRun = new DeletedRun { Author = author, Date = date, Id = (id++).ToString() };
                    delRun.AppendChild(new DeletedText(textElem.Text));
                    para.InsertBefore(delRun, run);

                    // Вставить новый текст
                    var newText = textElem.Text.Replace("⚠️", "⛔ КРИТИЧЕСКАЯ ЗАВИСИМОСТЬ:");
                    var insRun = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
                    var newRun = new Run(new Text(newText) { Space = SpaceProcessingModeValues.Preserve });
                    insRun.AppendChild(newRun);
                    para.InsertBefore(insRun, run);

                    run.Remove();

                    // Применить желтый фон к параграфу
                    if (para.ParagraphProperties == null)
                    {
                        para.ParagraphProperties = new ParagraphProperties();
                    }

                    var shading = para.ParagraphProperties.GetFirstChild<Shading>();
                    if (shading == null)
                    {
                        shading = new Shading();
                        para.ParagraphProperties.AppendChild(shading);
                    }

                    // Бледно-желтый цвет (светло-желтый)
                    shading.Fill = "FFF9C4";  // Светло-желтый
                    shading.Val = ShadingPatternValues.Clear;

                    count++;
                    Console.WriteLine($"  ✅ [{count:2d}] {text.Substring(0, Math.Min(80, text.Length))}...");
                    break;
                }
            }
        }
    }
}

doc.MainDocumentPart.Document.Save();
doc.Dispose();

Console.WriteLine();
Console.WriteLine(new string('=', 60));
Console.WriteLine($"✅ {count} параграфов переоформлено");
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine($"💾 {System.IO.Path.GetFileName(backup)}");
Console.WriteLine(new string('=', 60));
