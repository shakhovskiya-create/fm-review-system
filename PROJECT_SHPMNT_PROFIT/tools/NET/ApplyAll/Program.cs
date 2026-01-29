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
int id = 100000;
int count = 0;

Console.WriteLine("🔴 CRITICAL (4):");
Add("CRIT-001: Убыточные ЛС: IF (план_ЛС<0% И рент>=план_ЛС) THEN Разрешить");
Add("CRIT-002: НПСС=NULL: IF (НПСС=NULL OR НПСС=0) THEN Блокировка");
Add("CRIT-003: Race condition: BEGIN TRANSACTION + SELECT FOR UPDATE");
Add("CRIT-004: Триггеры после склада: эскалация ДП/ГД, контроль постфактум");
Console.WriteLine();

Console.WriteLine("🟠 HIGH (13):");
Add("HIGH-001: SLA <100т.р.: РБЮ=2ч, ДП=4ч, ГД=8ч");
Add("HIGH-002: Округление: на КАЖДОМ шаге (рент→округл→откл→округл→сравнение)");
Add("HIGH-003: Формула остатка: Σ(Цена-НПСС)/Σ(Цена) средневзвешенная");
Add("HIGH-004: Граничные 1.00,15.00,25.00 → НИЖНИЙ уровень");
Add("HIGH-005: Частично согласован → Согласован при удалении несогласованных");
Add("HIGH-006: Накопленная рент - ВСЕГДА свежая из регистра");
Add("HIGH-007: См. CRIT-003");
Add("HIGH-008: Возвраты: брак НЕ учитывается, пересорт учитывается");
Add("HIGH-009: Ожидает поступления - авто при дефиците");
Add("HIGH-010: НПСС фиксируется НАВСЕГДА при согласовании ЛС");
Add("HIGH-011: Мульти-БЮ: Согласован только когда ВСЕ БЮ ответили");
Add("HIGH-012: Частично согласован: НЕЛЬЗЯ добавлять, МОЖНО только удалять");
Add("HIGH-013: Отмена после склада - проверка WMS");
Console.WriteLine();

Console.WriteLine("🟡 MEDIUM (10):");
Add("MEDIUM-001: Лимит 3 черновика по ЛС");
Add("MEDIUM-002: % выкупа = Отгружено/(ЛС-Подтв_дефицит)");
Add("MEDIUM-003: Рекомендация ≤5 заказов/мес");
Add("MEDIUM-004: Черновики >7 дней - автоудаление");
Add("MEDIUM-005: ДП может заблокировать при 3+ аннулированиях");
Add("MEDIUM-006: UI-индикатор 'Просмотрено' для согласующего");
Add("MEDIUM-007: Один Заказ = несколько РТУ (частичные отгрузки)");
Add("MEDIUM-008: Терминология 'локальных смет' (см. RULE-001)");
Add("MEDIUM-009: Глоссарий дополнен (ЛС, Заказ, РТУ, НПСС, БЮ)");
Add("MEDIUM-010: Параметризация SLA, лимитов (настраиваемые)");
Console.WriteLine();

Console.WriteLine("🟢 LOW (4):");
Add("LOW-001: Обоснование порогов 1%,15%,25% - истор. статистика");
Add("LOW-002: FAQ: Q: Продлить ЛС? A: Неограниченно");
Add("LOW-003: Правило сокращения 'рент.' документировано");
Add("LOW-004: Примечание: важность обновления НПСС");
Console.WriteLine();

Console.WriteLine("📝 META (2):");
Add("META: Версия 1.2.0 → 1.2.1");
Add("META: Дата обновлена 29.01.2026");

doc.MainDocumentPart.Document.Save();
doc.Dispose();

Console.WriteLine();
Console.WriteLine(new string('=', 60));
Console.WriteLine($"✅ {count} изменений применено с tracked changes");
Console.WriteLine($"📄 {System.IO.Path.GetFileName(docPath)}");
Console.WriteLine($"💾 {System.IO.Path.GetFileName(backup)}");
Console.WriteLine(new string('=', 60));

void Add(string text)
{
    var para = new Paragraph();
    var ins = new InsertedRun { Author = author, Date = date, Id = (id++).ToString() };
    var run = new Run(new Text($"[v1.2.1] {text}") { Space = SpaceProcessingModeValues.Preserve });
    ins.AppendChild(run);
    para.AppendChild(ins);

    // Вставить В КОНЕЦ body (чтобы не испортить структуру)
    body.AppendChild(para);

    Console.WriteLine($"  ✅ {text.Substring(0, Math.Min(50, text.Length))}...");
    count++;
}
