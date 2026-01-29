using System;
using System.Linq;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Wordprocessing;

var docPath = args[0];
Console.WriteLine($"Открываю: {System.IO.Path.GetFileName(docPath)}");

var doc = WordprocessingDocument.Open(docPath, true);
var body = doc.MainDocumentPart.Document.Body;

// CRIT-002: После "Показатели рентабельности"
InsertAfterHeading("Показатели рентабельности", @"
БЛОКИРОВКА при НПСС=NULL:
IF (НПСС = NULL OR НПСС = 0) THEN Ошибка + блокировка добавления позиции
");

// CRIT-001: После "Критерии срабатывания"
InsertAfterHeading("Критерии срабатывания", @"
ПРАВИЛО для убыточных ЛС:
IF (план_ЛС < 0% И рент_Заказа >= план_ЛС) THEN Разрешить
");

// HIGH-001: После "SLA"
InsertAfterHeading("SLA", @"
SLA для заказов <100 т.р.: РБЮ=2ч, ДП=4ч, ГД=8ч
");

doc.MainDocumentPart.Document.Save();
Console.WriteLine("✅ 3 изменения добавлены");

void InsertAfterHeading(string heading, string text)
{
    var para = body.Descendants<Paragraph>().FirstOrDefault(p =>
        p.ParagraphProperties?.ParagraphStyleId?.Val?.Value?.Contains("Heading") == true &&
        p.InnerText.Contains(heading));

    if (para != null)
    {
        var newPara = new Paragraph(new Run(new Text(text.Trim())));
        body.InsertAfter(newPara, para);
        Console.WriteLine($"✓ {heading}");
    }
}
