# Google Autocomplete

מערכת להשלמת משפטים מתוך מאגר טקסט גדול. המערכת מחזירה עד חמש תוצאות,
תומכת בהתאמה מדויקת או בטעות אחת, ושומרת את המשפט המקורי, נתיב המקור,
מספר השורה והציון.

## מבנה המערכת

המערכת מחולקת לשני שלבים:

- **Offline:** קריאת קובצי הטקסט, נרמול המשפטים ובניית אינדקסי N-grams.
- **Online:** סינון מועמדים, בדיקת התאמה, חישוב ציון והחזרת Top-5.

קיימים שלושה מצבי הרצה:

1. Python מלא — טעינת הטקסט ובניית האינדקס ב-Python.
2. Native — טעינת הטקסט ב-Python ובניית האינדקס ב-C++.
3. Protobuf — טעינת קובצי Protobuf ובניית האינדקס ישירות ב-C++.

מצב Protobuf הוא המצב המהיר והמומלץ למאגר הגדול.

## דרישות

- Python 3.10 ומעלה.
- Visual Studio Community עם `Desktop development with C++`.
- MSVC, Windows SDK וכלי CMake.

מתוך תיקיית `project`:

```powershell
python -m pip install -r requirements-dev.txt
```

## בדיקות

בדיקות Python:

```powershell
python -m pytest -q
```

בנייה ובדיקות C++:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_native.ps1
```

הסקריפט מאתר את Visual Studio, מתקין את תלויות Protobuf ב-cache נפרד,
מקמפל את ה-DLL ומריץ את בדיקת C++.

## הפעלה עם קובצי טקסט

Python בלבד:

```powershell
python -m src.main "C:\path\to\corpus"
```

אינדקס C++:

```powershell
python -m src.main "C:\path\to\corpus" --native
```

## המרה ל-Protobuf

יש לבצע את ההמרה פעם אחת. תיקיית הפלט צריכה להיות חדשה או ריקה:

```powershell
python -m src.protobuf_store `
  "C:\path\to\corpus" `
  "C:\path\to\protobuf-output"
```

ברירת המחדל היא 50,000 משפטים בכל chunk. אפשר לשנות אותה:

```powershell
python -m src.protobuf_store `
  "C:\path\to\corpus" `
  "C:\path\to\protobuf-output" `
  --chunk-size 25000
```

## הפעלה מומלצת

לאחר ההמרה:

```powershell
python -m src.main --protobuf "C:\path\to\protobuf-output"
```

- Enter מציג השלמות עבור הקלט שנכתב.
- הקלט החדש מתווסף לקלט הקודם.
- `#` מאפס את המשפט.
- `Ctrl+C` מסיים את התוכנית.

## חלוקת הרכיבים

- `src/loader.py` — טעינת קבצים ומשפטים.
- `src/normalization.py` — נרמול טקסט.
- `src/indexer.py` — אינדקס N-grams ב-Python.
- `src/matcher.py` — בדיקת טעות אחת וחישוב ציון.
- `src/autocomplete.py` — תזמור החיפוש, Top-5 ומיון.
- `src/main.py` — ממשק שורת הפקודה.
- `src/protobuf_store.py` — שמירה וטעינה של chunks.
- `src/native_index.py` — החיבור בין Python ל-DLL.
- `native/` — מנוע האינדקס ב-C++.
- `proto/corpus.proto` — חוזה הנתונים של Protobuf.

## ביצועים על המאגר המלא

המדידה בוצעה על 2,583,987 משפטים:

| מדד | Python | C++ + Protobuf |
|---|---:|---:|
| טעינה ובניית אינדקס | 52.2 שניות | 21.9 שניות |
| תוספת RAM | 2,539.6 MiB | 2,119.8 MiB |
| קלט `a` | 616ms | 218ms |
| קלט `the` | 310ms | 120ms |
| קלט ארוך מדויק | 22.1ms | 7.2ms |

פרטי הפרופיילינג והמדידות המלאות נמצאים ב-`STAGE_B.md`.

## מבנה קובצי Protobuf

כל `SentenceRecord` כולל:

- מזהה משפט.
- המשפט המקורי.
- המשפט המנורמל.
- נתיב קובץ המקור.
- מספר השורה.
- גרסת casefold לצורך מיון עקבי.

המאגר מחולק ל-chunks כדי למנוע הודעה בינארית ענקית, לאפשר קריאה הדרגתית
ולהגביל את הזיכרון הזמני בזמן ההמרה.
