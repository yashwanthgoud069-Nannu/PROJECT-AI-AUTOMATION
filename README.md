# Kirana Voice Assistant

A voice billing assistant for small kirana shops. The shopkeeper speaks or types in **Telugu, Hindi or English**, including local slang and numbers said in any of the three languages. The assistant builds the bill, checks stock and prices, keeps the **khata** (credit book), shows today's sales and answers back out loud.

It runs on one computer and uses only the Python standard library, so there is nothing to `pip install`.

## Features

- **Billing by voice in three languages**: native script or typed in English letters, e.g. `రెండు కిలోల బియ్యం వేయి`, `dedh kilo aata aur 6 ande`, `add 2 kg rice and 3 milk packets`.
- **Numbers the way people say them**: `rendu`, `moodu`, `రెండున్నర` (2½), `ara kilo` (½), `pavu` (¼), `oka dozen` (12), `do`, `teen`, `dedh` (1½), `dhai` (2½), `sava kilo` (1¼), `twenty five`, `500 grams`, `2,000`.
- **Stock**: 18 common products with names in English, Telugu and Hindi. Edit price or stock in the table or by voice. Low and out-of-stock items are flagged.
- **Bill**: + / − on every line, say `vaddu` to undo the last item, print the bill. **Bill paid** reduces stock and adds to today's sales.
- **Khata**: put a bill on a customer's khata, take payments by voice or button, see a dated history for each customer, delete a customer. Names are matched by sound across scripts (Ramesh = రమేష్ = रमेश), but similar names like Rakesh and Ramesh are never mixed up.
- **Today's sales**: cash vs khata, khata payments received, items sold, and every bill with its time.
- **Replies in the language you spoke**, read out loud by the browser.

## Quick start

You need:
- Python 3.9 or newer
- Google Chrome or Microsoft Edge (for the microphone and spoken replies)
- An internet connection for speech recognition (the browser's online service turns speech into text)

From the project folder:

```bash
python kirana_assistant/app.py
```

Your browser opens **http://127.0.0.1:8000**. Keep the terminal window open while you use it, and press `Ctrl+C` there to stop.

> Always use that address. Opening `index.html` directly as a file cannot work: the page needs `app.py` running behind it, and it shows a red note if it can't reach it.

## Using it

1. Pick the language you will **speak** (top right: తెలుగు / हिन्दी / English).
2. Tap the green mic, or press `Space`, and speak. Or type in the box.
3. Items appear in the **Bill**. Finish with **Bill paid ✓**, or type a name and click **Add to khata**.

### Things you can say

| To… | Telugu | Hindi | English |
|---|---|---|---|
| Add items | `రెండు కిలోల బియ్యం వేయి` · `biyyam okatinnara kilo esey` | `दो किलो चावल डालो` · `dedh kilo aata aur 6 ande` | `add 2 kg rice and 3 milk packets` |
| Ask a price | `చక్కెర ధర ఎంత` | `चीनी का दाम क्या है` | `price of sugar` |
| Check stock | `పాలు ఎన్ని ఉన్నాయి` | `doodh kitna bacha hai` | `how much oil is left` |
| Remove | `సబ్బు తీసేయ్` · `vaddu` (last item) | `अंडे हटाओ` | `remove 1 milk` |
| Bill total | `మొత్తం ఎంత అయింది` | `कुल कितना हुआ` | `total` |
| Bill paid | `బిల్లు అయిపోయింది` | `हो गया` | `bill paid` |
| Restock / change price | `biyyam stock 20 kilo add` | `चावल का रेट 65 करो` | `set rice price 62` |
| Put bill on khata | `రమేష్ ఖాతాలో రాసుకో` | `रमेश के खाते में लिखो` | `put it on Ramesh's khata` |
| Khata payment | `రమేష్ 100 రూపాయలు ఇచ్చాడు` | `रमेश ने 100 दिए` | `Ramesh paid 100` |
| One customer's dues | `రమేష్ బాకీ ఎంత` | `रमेश का कितना उधार` | `how much does Ramesh owe` |
| Everyone's dues | `ఖాతా బాకీ ఎంత` | `उधार कितना है` | `khata dues` |
| Today's sales | `ఈరోజు అమ్మకాలు` | `आज की बिक्री` | `today sales` |
| Examples | `సహాయం` | `मदद` | `help` |

### Khata (credit book)

- **Add to khata**: under the bill, type the customer's name and click **Add to khata**, or say it. Names you've used before are suggested.
- **Khata tab**: lists everyone and what they owe. Tap a name to record a payment and see their history: date, time, what they bought, amount and balance after each entry.
- **Settled customers** stay in the list (marked *Settled*), so their history is kept. **Delete customer** removes them after asking you to confirm.
- **No deleting by voice**: on purpose, so a misheard name can't wipe someone's record.

### Today's sales

The **Today's sales** card shows the total plus `bills · cash · khata`. Tap it for the day's details: cash bills, sales on khata, khata payments received, cash collected (what should be in the drawer), items sold, and every bill and payment with its time. It starts fresh each day.

## Your data and privacy

- Everything is saved in `kirana_assistant/shop_data.json` after every change: stock, prices, the open bill, khata and today's sales. To back up, copy this file.
- That file is listed in `.gitignore`, so customer names and sales are never pushed to GitHub.
- The server only listens on `127.0.0.1`, so other devices on the network can't open it.
- Speech: the microphone is on only while the mic button is red. The browser sends that audio to its speech service (Google for Chrome, Microsoft for Edge) to turn it into text.

## Trying changes safely

Run a separate copy with its own data file and port, so your real shop data isn't touched:

```bash
python kirana_assistant/app.py --port 8765 --data kirana_assistant/test_shop.json
```

Run the built-in self-check (it covers numbers, slang, billing, khata and sales):

```bash
python kirana_assistant/app.py test
```

## Customising

All in `kirana_assistant/app.py`. Run the self-check after any change.

| To change… | Edit |
|---|---|
| Products, names, units, starting prices and stock, and the words people use for them | `CATALOG`: one line per product |
| Words that trigger actions (add, remove, price, khata, paid…) | `KEYWORDS` |
| Replies, including shop timings | `MSG` |
| When stock counts as "low" | `LOW_STOCK` |

Example: to add **ghee**, add a line to `CATALOG`:

```python
("ghee", "Ghee", "నెయ్యి", "घी", "kg", 650, 5, "ghee | neyyi నెయ్యి | ghee घी"),
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Red note "server is not running", clicks do nothing | Start `python kirana_assistant/app.py` and use http://127.0.0.1:8000 |
| `Port 8000 is busy` | It's already running in another window; open the address. Or use `--port 8001` |
| Mic button greyed out | Use Chrome or Edge |
| "Please allow microphone access" | Click the icon left of the address bar → allow Microphone |
| "Voice recognition needs an internet connection" | Speech-to-text is online; check the connection, or type instead |
| Replies spoken in English instead of Telugu/Hindi | No voice for that language is installed. Microsoft Edge usually includes Telugu and Hindi voices |
| A word or phrase isn't understood | Add it to `KEYWORDS` or to the product's words in `CATALOG` |

## How it works

```
mic → browser speech-to-text → POST /api/chat → app.py
        app.py: split words → turn number words into numbers → find products
                and the intent (add, price, khata…) → update bill / stock / khata
                → reply in English, Telugu and Hindi
     → page updates → browser speaks the reply
```

Understanding is rule-based (word lists plus a sound-alike match for customer names), not an AI model. It works offline apart from speech recognition, costs nothing to run, and is easy to extend by adding words.

## Project files

```
kirana_assistant/
  app.py          server, language understanding, shop logic, self-check
  index.html      the dashboard: assistant, bill, khata, stock, today's sales
  shop_data.json  your shop data (created on first use, not in git)
.claude/launch.json   preview setups: normal and test copy
voice.py          console version built while following the guide
main.py           rock-paper-scissors practice
Practice/         practice snippets
2026-11-11_kirana_shop_voice_assistant_guide.pdf   the guide this project started from
```

## Limitations

- Phrases far from the word lists won't be understood until the words are added.
- Built for one counter on one computer, with no user accounts.
- The same customer spelled in two scripts is matched by sound, but two different people with near-identical names need full names to be told apart.
