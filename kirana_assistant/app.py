"""
Kirana Voice Assistant - billing helper for a small kirana shop.

Understands Telugu, Hindi and English (in native script or typed in English letters),
common shop slang, and numbers said in any of the three languages
("rendunnara kilo", "dedh kilo", "two and a half", "500 grams", "oka dozen").

    python app.py         -> starts the server and opens http://127.0.0.1:8000 (use Chrome or Edge)
    python app.py test    -> run the self-check

Always open the page through that address while app.py is running. Opening index.html
directly as a file cannot work: the page needs this server to answer.

Only the Python standard library is used. The browser does speech-to-text and
text-to-speech; respond() below is the shop "brain". Stock, prices, the open bill
and today's sales are saved to shop_data.json next to this file.
"""
import json
import os
import re
import sys
import unicodedata
import webbrowser
from datetime import date, datetime
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent


def flag(name, default):                          # --port 8001 / --data test.json, for trying things out safely
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default


PORT = int(flag("--port", 8000))
DATA_FILE = Path(flag("--data", HERE / "shop_data.json"))
LOW_STOCK = 5                      # stock at or below this is flagged "low"
LANGS = ("en", "te", "hi")         # every 3-part table below is in this order


def norm(s):
    return unicodedata.normalize("NFC", s).lower()


SEEN = (set(), set(), set())       # Latin-letter words per language, for language detection


def groups(spec):
    """'english | telugu | hindi' -> three word lists. '_' joins a phrase ("how_much")."""
    gs = [[norm(w.replace("_", " ")) for w in g.split()] for g in spec.split("|")]
    for seen, ws in zip(SEEN, gs):
        seen.update(w for w in ws if w.isascii() and " " not in w)
    return gs


# ---------------------------------------------------------------- products
# To add a product, add a line. Extra words = what people actually say (English | Telugu | Hindi).
# Telugu/Hindi script words match as prefixes, so "బియ్య" also catches "బియ్యం", "బియ్యాన్ని".
CATALOG = [
    # id         English          Telugu            Hindi          unit     price stock  extra words
    ("rice",     "Rice",          "బియ్యం",          "चावल",         "kg",     60, 50, "rice | biyyam biyam biyyamu బియ్య రైస్ | chawal chaval chawl राइस"),
    ("sugar",    "Sugar",         "చక్కెర",          "चीनी",         "kg",     48, 30, "sugar | chakkera chakera panchadara panchadaara పంచదార షుగర్ | chini cheeni shakkar शक्कर शुगर"),
    ("milk",     "Milk",          "పాలు",            "दूध",          "packet", 30, 24, "milk | palu paalu pala paala పాల మిల్క్ | doodh dudh dood मिल्क"),
    ("tea",      "Tea Powder",    "టీ పొడి",          "चाय पत्ती",     "packet", 120, 12, "tea | teepodi chaay చాయ్ ఛాయ్ | chai chay chaipatti टी"),
    ("atta",     "Wheat Atta",    "గోధుమ పిండి",      "आटा",          "kg",     45, 40, "atta wheat flour | godhuma godhumapindi pindi ఆటా | aata aatta gehun गेहूं"),
    ("toordal",  "Toor Dal",      "కంది పప్పు",       "तूर दाल",       "kg",     140, 20, "toordal lentil lentils | kandi kandipappu pappu | toor tur arhar अरहर"),
    ("oil",      "Sunflower Oil", "నూనె",            "तेल",          "litre",  150, 18, "oil | nune noone nuune ఆయిల్ | tel ऑयल आयल"),
    ("salt",     "Salt",          "ఉప్పు",           "नमक",          "packet", 25, 25, "salt | uppu సాల్ట్ | namak"),
    ("eggs",     "Eggs",          "గుడ్లు",           "अंडे",         "pc",     7,  60, "egg eggs | guddu guddulu gudlu గుడ్డు గుడ్ల ఎగ్ | anda ande anday अंड एग"),
    ("onion",    "Onion",         "ఉల్లిపాయలు",       "प्याज",        "kg",     40, 25, "onion | ulli ullipaya ullipayalu ullipaayalu ulligadda ulligaddalu ఉల్లి ఆనియన్ | pyaz pyaaz pyaj kanda अनियन"),
    ("potato",   "Potato",        "బంగాళాదుంపలు",    "आलू",          "kg",     30, 30, "potato potatoes | bangaladumpa bangala alugadda aalugadda బంగాళ ఆలుగడ్డ ఆలూ పొటాటో | aloo alu aalu पोटैटो पोटेटो"),
    ("bread",    "Bread",         "బ్రెడ్",           "ब्रेड",         "packet", 40, 4,  "bread | | "),
    ("noodles",  "Noodles",       "నూడుల్స్",         "नूडल्स",        "packet", 14, 40, "noodles maggi | మ్యాగీ మాగీ | मैगी"),
    ("biscuits", "Biscuits",      "బిస్కెట్లు",        "बिस्कुट",       "packet", 10, 50, "biscuit biscuits | biskettu బిస్కె బిస్కట్ | biskut biscut बिस्किट"),
    ("jaggery",  "Jaggery",       "బెల్లం",           "गुड़",          "kg",     70, 10, "jaggery | bellam | gud gur"),
    ("turmeric", "Turmeric",      "పసుపు",           "हल्दी",         "packet", 30, 3,  "turmeric | pasupu | haldi"),
    ("chilli",   "Chilli Powder", "కారం",            "मिर्च पाउडर",   "packet", 40, 15, "chilli chili | karam kaaram | mirchi mirch"),
    ("soap",     "Soap",          "సబ్బు",           "साबुन",         "pc",     35, 30, "soap | sabbu sabbulu సబ్బ సోప్ | sabun saabun सोप"),
]
UNITS = {"kg": ("kg", "కిలో", "किलो"), "litre": ("litre", "లీటర్", "लीटर"),
         "packet": ("packet", "ప్యాకెట్", "पैकेट"), "pc": ("pc", "పీస్", "पीस")}

PRODUCTS = {}   # id -> {"names": (en, te, hi), "unit", "price", "stock"}
ALIASES = []    # (word, id), longest first
for pid, en, te, hi, unit, price, stock, words in CATALOG:
    PRODUCTS[pid] = {"names": (en, te, hi), "unit": unit, "price": float(price), "stock": float(stock)}
    en_w, te_w, hi_w = groups(words)
    ALIASES += [(w, pid) for w in en_w + [pid] + te_w + hi_w + norm(te).split() + norm(hi).split()]
ALIASES.sort(key=lambda a: -len(a[0]))

# ---------------------------------------------------------------- what the shopkeeper wants
KEYWORDS = {
    "khata":    "khata khaata khatha katha credit udhaar udhar owe owes due dues account"
                " | khata khaata khatha katha appu baki baaki ఖాత అప్పు బాకీ బాకి"
                " | khata khaata khate khaate udhaar udhar udhari baki baaki उधार खाता खाते बाकी बकाया",
    "paid":     "paid pay payment received gave got returned deposit deposited"
                " | ichhadu ichhindi ichharu icharu kattadu kattindi kattaru jama vachindi vachayi vachai teesukunna tisukunna"
                " ఇచ్చ కట్టా కట్టి జమ వచ్చ తీసుకున్న పేమెంట్"
                " | diye diya de_diye jama chukaya chuka mile mila aaye aye liye दिए दिया जमा चुकाया चुका मिले मिला आए आये लिए पेमेंट",
    "checkout": "checkout check_out paid done bill_paid payment_done"
                " | ayipoyindi aipoyindi ayipoindi ichharu icharu అయిపోయింది అయిపొయింది ఇచ్చారు పెయిడ్ పేమెంట్"
                " | ho_gaya hogaya mil_gaye mil_gaya हो_गया मिल_गए मिल_गया पेड पेमेंट",
    "clear":    "clear reset new_bill cancel_bill | kotha_bill kottha_bill కొత్త_బిల్ క్లియర్ | naya_bill नया_बिल क्लियर",
    "remove":   "remove delete cancel minus undo"
                " | teesey teeseyi tisey tiseyi teesesey tiyyi vaddu vadhu తీసే తీసెయ్ తీసి తియ్ వద్దు రిమూవ్ క్యాన్సిల్ కాన్సిల్"
                " | hatao hata hatado nikalo nikal nahi_chahiye हटा निकाल नहीं_चाहिए रिमूव कैंसल",
    "all":      "all everything | anni అన్నీ అన్ని | sab sabhi pura सब सारा पूरा",
    "set":      "set change update make | marchu cheyi chey cheyyi cheyandi pettu మార్చు చేయ చెయ్ పెట్టు"
                " | badlo badal karo kar kardo बदल करो कर",
    "price":    "price rate cost | dhara dara rate ధర రేటు రేట్ ప్రైస్ | daam dam bhav bhaav kimat keemat rate दाम भाव कीमत रेट प्राइस",
    "add":      "add give want need put"
                " | veyyi veyi vey eyyi esey eseyi kavali kaavali kavale ivvu ivvandi iyyi iyyu pettu kalupu rasko raasko inko inkoka"
                " వెయ్ వేయ వేసి ఏసెయ్ ఏసేయ్ ఎయ్యి కావాల కావలె ఇవ్వ ఇయ్యి పెట్టు కలుపు రాసుకో యాడ్ ఇంకో ఇంకొక"
                " | dalo daalo jodo jod likho chahiye chaiye dena de_do dal_do daal_do डालो डाल जोड़ लिखो लिख चाहिए चाहिये देना दे_दो ऐड एड",
    "howmuch":  "how_much | entha enta enthaki ఎంత | kitna kitne kitni कितना कितने कितनी",
    "stockword": "stock inventory | stock saruku nilva స్టాక్ సరుకు నిల్వ | stock maal स्टॉक माल",
    "stock":    "stock available availability have left remaining how_many"
                " | unda undha undaa unnaya unnaaya undi unnayi enni ఉందా ఉన్నాయా ఉంది ఉన్నాయి ఎన్ని"
                " | hai_kya milega milegi bacha bache available है_क्या मिलेगा मिलेगी बचा बचे उपलब्ध",
    "total":    "total bill cart amount | billu mottham motham lekka మొత్తం బిల్ లెక్క టోటల్ కార్ట్ | kul hisab hisaab बिल कुल हिसाब टोटल कार्ट",
    "sales":    "sales sale collection earnings | ammakalu ammakam galla అమ్మక గల్లా కలెక్షన్ సేల్ | bikri kamai बिक्री कमाई सेल कलेक्शन",
    "greet":    "hello hi hey | namaskaram namaste హలో హాయ్ నమస్కా నమస్తే | namaskar नमस्ते नमस्कार हेलो हाय",
    "timing":   "timing timings time open | samayam టైమ్ టైం టైమింగ్ సమయం | samay khulega समय टाइम खुल",
    "help":     "help | sahayam సహాయం హెల్ప్ | madad मदद हेल्प",
    "thanks":   "thanks thank bye | dhanyavadalu థాంక్స్ ధన్యవాద బై | dhanyavad shukriya धन्यवाद शुक्रिया बाय",
}
KW = {intent: [w for g in groups(spec) for w in g] for intent, spec in KEYWORDS.items()}

# ---------------------------------------------------------------- numbers in three languages
NUMBERS = [
    (1, "one | okati oka okka okkati ఒకటి ఒక ఒక్క ఒక్కటి | ek एक"),
    (2, "two | rendu రెండు | do दो"),
    (3, "three | moodu mudu మూడు | teen तीन"),
    (4, "four | naalugu nalugu నాలుగు | char chaar चार"),
    (5, "five | aidu ayidu ఐదు అయిదు | paanch panch paach पांच पाँच"),
    (6, "six | aaru aru ఆరు | chhe chhah chah छह छः छे"),
    (7, "seven | edu yedu ఏడు | saat सात"),
    (8, "eight | enimidi ఎనిమిది | aath आठ"),
    (9, "nine | tommidi తొమ్మిది | nau नौ"),
    (10, "ten | padi padhi పది | das दस"),
    (11, "eleven | padakondu పదకొండు | gyarah ग्यारह"),
    (12, "twelve | pannendu పన్నెండు | barah बारह"),
    (13, "thirteen | padamudu పదమూడు | terah तेरह"),
    (14, "fourteen | padnalugu పద్నాలుగు | chaudah चौदह"),
    (15, "fifteen | padihenu పదిహేను | pandrah पंद्रह"),
    (16, "sixteen | padaharu పదహారు | solah सोलह"),
    (17, "seventeen | padihedu పదిహేడు | satrah सत्रह"),
    (18, "eighteen | paddenimidi పద్దెనిమిది | atharah अठारह"),
    (19, "nineteen | pandommidi పందొమ్మిది | unnis उन्नीस"),
    (20, "twenty | iravai iruvai ఇరవై | bees बीस"),
    (25, " | | pachees pachis पच्चीस"),
    (30, "thirty | muppai ముప్పై | tees तीस"),
    (40, "forty | nalabhai nalabai నలభై | chalis chaalis चालीस"),
    (50, "fifty | yabhai yabai ebhai యాభై | pachas pachaas पचास"),
    (60, "sixty | aravai అరవై | साठ"),
    (70, "seventy | debbai డెబ్బై | sattar सत्तर"),
    (80, "eighty | enabhai enabai ఎనభై | assi अस्सी"),
    (90, "ninety | tombhai tombai తొంభై | nabbe नब्बे"),
    (100, "hundred | vanda vandha vandalu nooru వంద వందలు వందల నూరు | sau सौ"),
    (0.5, "half | ara arakilo nnara అర అరకిలో అరకేజీ న్నర | aadha adha aadhi adhi आधा आधी"),
    (0.25, "quarter | pavu paavu pavukilo పావు పావుకిలో | paav पाव"),
    (0.75, " | muppavu ముప్పావు | "),
    (1.5, " | | dedh derh डेढ़"),
    (2.5, " | | dhai dhaai ढाई"),
]
NUM = {w: float(v) for v, spec in NUMBERS for g in groups(spec) for w in g}
SAVA, PAUNE = {norm(w) for w in ("sava", "sawa", "सवा")}, {norm(w) for w in ("paune", "पौने")}  # +1/4, -1/4
GRAMS = {norm(w) for w in "g gm gms gram grams gramulu ml గ్రాము గ్రాములు గ్రాముల ग्राम".split()}
DOZEN = {norm(w) for w in "dozen dozens darjan dazan dajan డజను డజన్ दर्जन डजन डज़न".split()}
FILLER = {norm(w) for w in "and a an aur mariyu inka & और మరియు ఇంకా".split()}
STOP = {norm(w) for w in (                      # words that are never part of a customer's name
    "this it the on to in into of s my his her please mr mrs customer name how much many does do did is are was what who whose"
    " from rupees rupee rs money cash"
    " ee aa ni nu lo ki ku di du ga garu gari andi anna akka em emi enti evaru evari peru kastamar nundi daggara"
    " rupayalu rupayi dabbulu paisalu"
    " ఈ ఆ ని ను లో కి కు ది గారు గారి అండి అన్న అక్క ఏమి ఏంటి ఎవరు ఎవరి పేరు కస్టమర్ నేమ్ నుండి నుంచి దగ్గర"
    " రూపాయలు రూపాయి డబ్బులు పైసలు ₹"
    " ye yeh is isko iska iske ko ka ke ki mein me main par pe ji bhai bhaiya ne hai hain tha kya kaun kiska naam se"
    " rupaye rupaiye paise"
    " ये यह इस इसको इसका को का के की में पर पे जी भाई भैया ने है हैं था क्या कौन किसका नाम ग्राहक कस्टमर से"
    " रुपये रुपए रुपया पैसे").split()}

# Telugu and Devanagari share one Unicode layout (Telugu = Devanagari + 0x300), so one table spells both in Latin.
CONS = dict(p.split("=") for p in "क=k ख=kh ग=g घ=gh ङ=n च=ch छ=chh ज=j झ=jh ञ=n ट=t ठ=th ड=d ढ=dh ण=n त=t थ=th "
            "द=d ध=dh न=n ऩ=n प=p फ=ph ब=b भ=bh म=m य=y र=r ऱ=r ल=l ळ=l ऴ=l व=v श=sh ष=sh स=s ह=h".split())
VOWELS = dict(p.split("=") for p in "अ=a आ=aa इ=i ई=ii उ=u ऊ=uu ऋ=ri ए=e ऐ=ai ओ=o औ=au ऎ=e ऒ=o ऍ=e ऑ=o ं=n ँ=n ः=h".split())
MATRAS = dict(p.split("=") for p in "ा=aa ि=i ी=ii ु=u ू=uu ृ=ri े=e ै=ai ो=o ौ=au ॆ=e ॊ=o ॅ=e ॉ=o".split())
VIRAMA, NUKTA = "्", "़"
DO_VERBS = {norm(w) for w in "de kar dal daal le hata nikal bata dikha bana jod likh rakh दे कर डाल ले हटा निकाल बता दिखा बना जोड़ लिख रख".split()}
NOT_AFTER_DO = {"you", "not", "it", "this", "that"}
DIGITS = str.maketrans("०१२३४५६७८९౦౧౨౩౪౫౬౭౮౯", "01234567890123456789")
ROMAN = {"te": SEEN[1] - SEEN[2] - SEEN[0], "hi": SEEN[2] - SEEN[1] - SEEN[0] - {"do"}}

# ---------------------------------------------------------------- replies (English, Telugu, Hindi)
MSG = {
    "added":       ("Added {x}.", "{x} వేశాను.", "{x} जोड़ दिया।"),
    "removed":     ("Removed {x}.", "{x} తీసేశాను.", "{x} हटा दिया।"),
    "short":       ("Only {s} {name} left.", "{name} {s} మాత్రమే ఉంది.", "{name} सिर्फ़ {s} बचा है।"),
    "out":         ("{name} is out of stock.", "{name} స్టాక్ లేదు.", "{name} स्टॉक में नहीं है।"),
    "not_in_bill": ("{name} is not in the bill.", "{name} బిల్లులో లేదు.", "{name} बिल में नहीं है।"),
    "empty":       ("The bill is empty.", "బిల్లు ఖాళీగా ఉంది.", "बिल खाली है।"),
    "total":       ("{n} items, total ₹{t}.", "{n} వస్తువులు, మొత్తం ₹{t}.", "{n} सामान, कुल ₹{t}।"),
    "price":       ("{name} is ₹{p} per {u}.", "{name} ఒక {u} ₹{p}.", "{name} ₹{p} प्रति {u} है।"),
    "price_q":     ("{q} {u} {name} costs ₹{amt}.", "{q} {u} {name} ₹{amt} అవుతుంది.", "{q} {u} {name} ₹{amt} का होगा।"),
    "stock":       ("{name}: {s} in stock.", "{name} {s} స్టాక్ ఉంది.", "{name} का स्टॉक {s} है।"),
    "low":         ("Low stock: {x}.", "తక్కువ స్టాక్: {x}.", "कम स्टॉक: {x}।"),
    "all_ok":      ("All items are well stocked.", "అన్ని సరుకులు సరిపడా ఉన్నాయి.", "सारा सामान पर्याप्त है।"),
    "restocked":   ("{name} stock is now {s}.", "{name} స్టాక్ ఇప్పుడు {s}.", "{name} का स्टॉक अब {s} है।"),
    "price_set":   ("{name} is now ₹{p} per {u}.", "{name} ధర ఒక {u} ₹{p} కి మార్చాను.", "{name} का दाम अब ₹{p} प्रति {u} है।"),
    "paid":        ("Bill of ₹{t} done. Stock updated.", "₹{t} బిల్లు పూర్తయింది. స్టాక్ తగ్గించాను.", "₹{t} का बिल पूरा हुआ। स्टॉक अपडेट हो गया।"),
    "cleared":     ("Started a new bill.", "కొత్త బిల్లు మొదలుపెట్టాను.", "नया बिल शुरू किया।"),
    "sales":       ("Today's sales: ₹{t} from {b} bills — cash ₹{cash}, on khata ₹{credit}. Khata payments received ₹{got}.",
                    "ఈరోజు అమ్మకాలు: {b} బిల్లులు, ₹{t} — నగదు ₹{cash}, ఖాతాలో ₹{credit}. ఖాతా వసూలు ₹{got}.",
                    "आज की बिक्री: {b} बिल, ₹{t} — नकद ₹{cash}, खाते में ₹{credit}। खाते से वसूली ₹{got}।"),
    "sales_top":   ("Top sellers: {x}.", "ఎక్కువ అమ్మినవి: {x}.", "सबसे ज़्यादा बिके: {x}।"),
    "khata_deleted": ("Deleted {who}'s khata.", "{who} ఖాతా తొలగించాను.", "{who} का खाता हटा दिया।"),
    "greet":       ("Hello! Tell me the items and I'll make the bill.", "నమస్కారం! సరుకులు చెప్పండి, బిల్లు వేస్తాను.",
                    "नमस्ते! सामान बताइए, बिल बन जाएगा।"),
    "timing":      ("The shop is open from 8 AM to 9 PM.", "షాపు ఉదయం 8 నుండి రాత్రి 9 వరకు తెరిచి ఉంటుంది.",
                    "दुकान सुबह 8 से रात 9 बजे तक खुली है।"),
    "help":        ("Try: add 2 kg rice, sugar price, how much milk is left, total, bill paid, put it on Ramesh's khata.",
                    "ఇలా చెప్పండి: రెండు కిలోల బియ్యం వేయి, చక్కెర ధర ఎంత, పాలు ఎన్ని ఉన్నాయి, మొత్తం ఎంత, బిల్లు అయిపోయింది, రమేష్ ఖాతాలో రాసుకో.",
                    "ऐसे बोलिए: दो किलो चावल डालो, चीनी का दाम, दूध कितना बचा, कुल कितना हुआ, हो गया, रमेश के खाते में लिखो।"),
    "khata_add":   ("Added ₹{t} to {who}'s khata. {who} now owes ₹{due}.", "₹{t} {who} ఖాతాలో రాశాను. {who} బాకీ ₹{due}.",
                    "₹{t} {who} के खाते में लिख दिया। {who} का बाकी ₹{due}।"),
    "khata_due":   ("{who} owes ₹{due}.", "{who} బాకీ ₹{due}.", "{who} का बाकी ₹{due} है।"),
    "khata_paid":  ("Received ₹{t} from {who}. Still due ₹{due}.", "{who} నుండి ₹{t} వచ్చింది. ఇంకా బాకీ ₹{due}.",
                    "{who} से ₹{t} मिले। बाकी ₹{due}।"),
    "khata_clear": ("Received ₹{t} from {who}. Khata fully settled.", "{who} నుండి ₹{t} వచ్చింది. ఖాతా పూర్తిగా తీరింది.",
                    "{who} से ₹{t} मिले। खाता पूरा चुकता हो गया।"),
    "khata_list":  ("{n} customers owe ₹{t}: {x}.", "{n} మంది బాకీ ₹{t}: {x}.", "{n} ग्राहकों का बाकी ₹{t}: {x}।"),
    "khata_none":  ("No khata dues.", "ఎవరి బాకీ లేదు.", "किसी का बाकी नहीं है।"),
    "khata_nobody": ("{who} has no khata dues.", "{who} కి బాకీ లేదు.", "{who} का कोई बाकी नहीं है।"),
    "khata_who":   ("Whose khata? Say the customer's name.", "ఎవరి ఖాతా? కస్టమర్ పేరు చెప్పండి.", "किसका खाता? ग्राहक का नाम बताइए।"),
    "khata_which": ("Which one: {who}? Say the full name.", "ఎవరు: {who}? పూర్తి పేరు చెప్పండి.", "कौन: {who}? पूरा नाम बताइए।"),
    "thanks":      ("Thank you! Come again.", "ధన్యవాదాలు! మళ్ళీ రండి.", "धन्यवाद! फिर आइए।"),
    "unknown":     ("Sorry, I didn't get that. Say 'help' for examples.", "క్షమించండి, అర్థం కాలేదు. ఉదాహరణల కోసం 'సహాయం' అనండి.",
                    "माफ़ कीजिए, समझ नहीं आया। उदाहरण के लिए 'मदद' बोलिए।"),
}

CART = {}                                                   # id -> qty
ADDED = []                                                  # add history, so "vaddu" / "undo" drops the latest
KHATA = {}                    # sound key -> {"name", "due", "history": [{"at", "amount", "balance", "items"?}]}
STATE = {"day": date.today().isoformat(), "sales": 0.0, "bills": 0,
         "today": []}          # today's bills and khata payments: {"at", "kind": cash|khata|payment, "amount", "items"?, "who"?}


# ---------------------------------------------------------------- understanding
def tokenize(text):
    t = norm(text).translate(DIGITS)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)                               # "2,000" / "1,00,000" -> one number
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " , ", t)                       # full stops -> boundary, keep 1.5
    t = re.sub(r"[,?!।|;:\"'()\[\]{}/\\-]+", " , ", t)                 # punctuation -> boundary
    t = re.sub(r"(?<=\d)(?=[^\d\s.,])|(?<=[^\d\s.,])(?=\d)", " ", t)  # "2kg" -> "2 kg"
    return [w for w in t.split() if w not in FILLER]


def value(t, prev, nxt):
    """The number a single token stands for, or None."""
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t)
    if t in ("do", "दो") and (nxt is None or nxt in NOT_AFTER_DO or prev in DO_VERBS):
        return None                                   # Hindi "do" is 2, but "de do" / "do you" are not
    if t in NUM:
        return NUM[t]
    for suffix in ("nnara", "nara", "న్నర"):           # Telugu "rendunnara" = two and a half
        if t.endswith(suffix) and t[: -len(suffix)] in NUM:
            return NUM[t[: -len(suffix)]] + 0.5
    return None


def numbers(toks):
    """Turn number words into floats, joining 'twenty five', '2 and half', '500 grams', 'oka dozen'."""
    out, spoken, i = [], False, 0          # spoken: out[-1] was said in words (so it may join the next)
    while i < len(toks):
        t, prev = toks[i], toks[i - 1] if i else None
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        last = out[-1] if out and isinstance(out[-1], float) else None
        i += 1
        if t in SAVA or t in PAUNE:                   # sava do = 2.25, paune do = 1.75, sava kilo = 1.25
            v = value(nxt, t, toks[i + 1] if i + 1 < len(toks) else None) if nxt else None
            i += v is not None
            out.append((1.0 if v is None else v) + (0.25 if t in SAVA else -0.25))
            spoken = False
            continue
        v = value(t, prev, nxt)
        if v is None:
            if t in GRAMS and last is not None:
                out[-1] = last / 1000
            elif t in DOZEN and last is not None:
                out[-1] = last * 12
            elif t in DOZEN:
                out.append(12.0)
            else:
                out.append(t)
            spoken = False
            continue
        word = not t[0].isdigit()
        if last is not None and v == 0.5 and last == int(last):
            out[-1] = last + 0.5
        elif last is not None and v == 100 and last < 100:
            out[-1] = last * 100
        elif last is not None and spoken and word and v == int(v) and (
                (20 <= last < 100 and last % 10 == 0 and v < 10) or (last >= 100 and last % 100 == 0 and v < 100)):
            out[-1] = last + v
        else:
            out.append(v)
            spoken = word
    return out


def hit(word, key):
    """Telugu/Hindi script keys match as prefixes (suffixes vary); English letters match whole words."""
    return word.startswith(key) if not key.isascii() else word in (key, key + "s")


def find_items(toks):
    """[[product id, qty or None], ...]. Numbers pair with the product next to them."""
    events = []
    for t in toks:
        e = t if isinstance(t, float) else next((pid for alias, pid in ALIASES if hit(t, alias)), None)
        if e is not None and not (isinstance(e, str) and events and events[-1] == e):   # "kandi pappu" = one item
            events.append(e)
    items = []
    if events and isinstance(events[0], float):       # "2 kilo rice, 1 kilo sugar"
        q = None
        for e in events:
            if isinstance(e, float):
                q = e
            else:
                items.append([e, q])
                q = None
    else:                                             # "biyyam rendu kilo, chakkera oka kilo"
        for e in events:
            if isinstance(e, str):
                items.append([e, None])
            elif items and items[-1][1] is None:
                items[-1][1] = e
    return items


def detect(raw, ui):
    joined = " ".join(raw)
    if re.search("[ఀ-౿]", joined):
        return "te"
    if re.search("[ऀ-ॿ]", joined):
        return "hi"
    te, hi = (sum(w in ROMAN[k] for w in raw) for k in ("te", "hi"))
    return "te" if te > hi else "hi" if hi > te else ui


# ---------------------------------------------------------------- shop actions
def cart_total():
    return round(sum(q * PRODUCTS[p]["price"] for p, q in CART.items()), 2)


def total_msg():
    return ("total", {"t": cart_total(), "n": len(CART)}) if CART else ("empty", {})


def stock_msg(pid):
    return ("stock" if PRODUCTS[pid]["stock"] > 0 else "out", {"pid": pid})


def low_msg():
    low = [(p, d["stock"]) for p, d in PRODUCTS.items() if d["stock"] <= LOW_STOCK]
    return ("low", {"items": low}) if low else ("all_ok", {})


def price_msgs(items):
    return [("price_q", {"pid": p, "q": q, "amt": round(q * PRODUCTS[p]["price"], 2)}) if q else ("price", {"pid": p})
            for p, q in items]


def add(items, out):
    added = []
    for pid, q in items:
        q = q or 1
        left = round(PRODUCTS[pid]["stock"] - CART.get(pid, 0), 3)
        if q > left:
            out.append(("short", {"pid": pid, "s": left}) if left > 0 else ("out", {"pid": pid}))
        else:
            CART[pid] = round(CART.get(pid, 0) + q, 3)
            ADDED.append(pid)
            added.append((pid, q))
    if added:
        out.insert(0, ("added", {"items": added}))


def remove(items, out):
    if not items:                                            # plain "vaddu" / "undo" -> drop the last item
        if not CART:
            return out.append(("empty", {}))
        items = [(next((p for p in reversed(ADDED) if p in CART), list(CART)[-1]), None)]
    gone = []
    for pid, q in items:
        if pid not in CART:
            out.append(("not_in_bill", {"pid": pid}))
            continue
        q = min(q or CART[pid], CART[pid])
        CART[pid] = round(CART[pid] - q, 3)
        if pid in ADDED:                                     # a removal cancels that item's latest add
            ADDED.pop(len(ADDED) - 1 - ADDED[::-1].index(pid))
        if CART[pid] <= 0:
            del CART[pid]
        gone.append((pid, q))
    if gone:
        out.insert(0, ("removed", {"items": gone}))


def now():
    return datetime.now().isoformat(timespec="minutes")


def checkout(customer=None):
    """Close the open bill: stock goes down, it counts in today's sales (paid in cash, or on customer's khata)."""
    total = cart_total()
    lines = [[p, q, round(q * PRODUCTS[p]["price"], 2)] for p, q in CART.items()]
    for pid, q in CART.items():
        PRODUCTS[pid]["stock"] = max(0.0, round(PRODUCTS[pid]["stock"] - q, 3))
    STATE["sales"] = round(STATE["sales"] + total, 2)
    STATE["bills"] += 1
    STATE["today"].append({"at": now(), "kind": "khata" if customer else "cash", "amount": total, "items": lines,
                           **({"who": customer} if customer else {})})
    CART.clear()
    return total


def today_summary():
    """Brief details of today's sales for the dashboard and the voice reply."""
    events = STATE["today"]
    total = {kind: round(sum(e["amount"] for e in events if e["kind"] == kind), 2) for kind in ("cash", "khata", "payment")}
    sold = {}                                                        # product -> [qty, amount]
    for e in events:
        for pid, q, amount in e.get("items", []):
            row = sold.setdefault(pid, [0.0, 0.0])
            row[0], row[1] = round(row[0] + q, 3), round(row[1] + amount, 2)
    recorded_bills = sum(e["kind"] != "payment" for e in events)
    return {"cash": total["cash"], "credit": total["khata"], "collected": total["payment"],
            "items": sorted(([p, q, a] for p, (q, a) in sold.items()), key=lambda r: -r[2]),
            "events": events,
            # sales made before this summary existed have no details; show them as one line
            "earlier": round(STATE["sales"] - total["cash"] - total["khata"], 2), "earlier_bills": STATE["bills"] - recorded_bills}


# ---------------------------------------------------------------- khata (credit book)
def latin(s):
    """Rough Latin spelling of Telugu/Devanagari text: "రమేష్" -> "ramesh", "रमेश" -> "ramesha"."""
    out, vowel_due = [], False                 # vowel_due: the last consonant still carries its built-in "a"
    for ch in s:
        if "ఀ" <= ch <= "౿":
            ch = chr(ord(ch) - 0x300)
        if ch in MATRAS or ch == VIRAMA:
            out.append(MATRAS.get(ch, ""))
            vowel_due = False
            continue
        if ch == NUKTA:
            continue
        if vowel_due:
            out.append("a")
        vowel_due = ch in CONS
        out.append(CONS.get(ch) or VOWELS.get(ch) or (ch if ch.isascii() else ""))
    return "".join(out) + ("a" if vowel_due else "")


def phon(name):
    """Sound key of a name, the same for "Lakshmi", "Laxmi", "లక్ష్మీ" and "लक्ष्मी"."""
    s = re.sub(r"[^a-z]", "", latin(norm(name)))
    for a, b in (("x", "ks"), ("q", "k"), ("z", "j"), ("w", "v"), ("ph", "f"), ("ee", "i"), ("oo", "u"),
                 ("ck", "k"), ("mb", "nb"), ("mp", "np"), ("h", "")):
        s = s.replace(a, b)
    s = re.sub(r"(?<=[aeiou])y(?=[aeiou]|$)", "", s)         # "saayi" = "sai"
    s = re.sub(r"(.)\1+", r"\1", s)                           # "aa" = "a", "ll" = "l"
    return s[:-1] if len(s) > 3 and s.endswith("a") else s    # "ramesha" (Hindi) = "ramesh"


PARTICLES = {phon(w) for w in "ki ku ni nu di du tho ga garu gari ji ne se ka ke ko".split()}  # "రమేష్‌కి"


def khata_key(name):
    return phon(name) or " ".join(norm(name).split())


def skip_word(w):
    """Commands, products and small words are never part of a customer's name."""
    return (w in STOP or any(hit(w, k) for ks in KW.values() for k in ks if " " not in k)
            or any(hit(w, a) for a, _ in ALIASES))


def display_name(name_words):
    name = " ".join(name_words)[:40]
    return name.title() if name.isascii() else name


def sound_match(said, name):
    if not said or not name:
        return 0.0
    if said == name or (said.startswith(name) and said[len(name):] in PARTICLES):
        return 1.0
    if min(len(said), len(name)) < 4:          # short names must match exactly
        return 0.0
    return SequenceMatcher(None, said, name).ratio()


def find_customer(name_words):
    """Khata customers named by these words, matched by sound. One key = clear match, several = ambiguous.
    The 0.85 bar lets "Yashwant"/"Yashwanth"/"యశ్వంత్" agree but keeps "Rakesh" off "Ramesh"'s khata."""
    said = [phon(w) for w in name_words]
    said += [a + b for a, b in zip(said, said[1:])]           # two-word names
    scores = {}
    for key, entry in KHATA.items():
        parts = [phon(w) for w in entry["name"].split() if norm(w) not in STOP]
        targets = [(key, 1.0)] + [(p, 0.99) for p in parts if p != key]   # full name beats first name
        scores[key] = max((sound_match(s, t) * weight for s in said for t, weight in targets), default=0.0)
    top = max(scores.values(), default=0.0)
    return [k for k, s in scores.items() if s == top] if top >= 0.85 else []


def log(entry, amount, items=None):
    entry["due"] = round(entry["due"] + amount, 2)
    entry["history"].append({"at": now(), "amount": round(amount, 2),
                             "balance": entry["due"], **({"items": items} if items else {})})


def to_khata(name):
    """Put the open bill on a customer's khata. Stock and today's sales update as for a paid bill."""
    name = " ".join(name.split())
    entry = KHATA.setdefault(khata_key(name), {"name": name, "due": 0.0, "history": []})
    items = [[p, q] for p, q in CART.items()]
    log(entry, checkout(entry["name"]), items)
    return ("khata_add", {"who": entry["name"], "t": entry["history"][-1]["amount"], "due": entry["due"]})


def khata_pay(key, amount):
    entry = KHATA[key]
    if entry["due"] <= 0:
        return ("khata_nobody", {"who": entry["name"]})
    paid = min(amount, entry["due"])
    log(entry, -paid)
    STATE["today"].append({"at": now(), "kind": "payment", "amount": paid, "who": entry["name"]})
    return ("khata_clear" if entry["due"] <= 0 else "khata_paid", {"who": entry["name"], "t": paid, "due": entry["due"]})


def delete_khata(key):
    """Remove a customer and their khata history (today's sales report keeps its lines)."""
    return ("khata_deleted", {"who": KHATA.pop(key)["name"]})


def khata_list():
    rows = sorted((e for e in KHATA.values() if e["due"] > 0), key=lambda e: -e["due"])
    if not rows:
        return ("khata_none", {})
    return ("khata_list", {"n": len(rows), "t": sum(e["due"] for e in rows),
                           "x": ", ".join(f"{e['name']} ₹{rupees(e['due'])}" for e in rows)})


def khata_intents(has, words, toks, items):
    """Khata replies for this sentence, or [] when it is not about the khata."""
    name_words = [w for w in words if not skip_word(w)]
    name = display_name(name_words)
    exact = khata_key(name) if name and khata_key(name) in KHATA else None
    found = [exact] if exact else find_customer(name_words)
    who = found[0] if len(found) == 1 else None
    amount = next((t for t in toks if isinstance(t, float)), None)
    paying = has("paid") and amount and not items
    if not (paying or has("khata")):
        return []
    if len(found) > 1 and len(name_words) <= 1:                     # "Sai" when there is Sai Kumar and Sai Ram
        return [("khata_which", {"who": " / ".join(KHATA[k]["name"] for k in found)})]
    if paying and (who or name):                                     # "Ramesh 200 ichhadu"
        return [khata_pay(who, amount) if who else ("khata_nobody", {"who": name})]
    if paying:                                                       # "500 ichharu" with no name: cash for the bill
        return []
    if CART and not has("howmuch"):                                  # "Ramesh khata lo rasko"
        if who and (exact or len(name_words) <= 1):
            return [to_khata(KHATA[who]["name"])]
        return [to_khata(name) if name else ("khata_who", {})]
    if who:                                                          # "Ramesh baki entha"
        e = KHATA[who]
        return [("khata_due", {"who": e["name"], "due": e["due"]}) if e["due"] > 0 else ("khata_nobody", {"who": e["name"]})]
    return [("khata_nobody", {"who": name}) if name else khata_list()]


def respond(text, ui="en"):
    raw = tokenize(text)
    toks = numbers(raw)
    words = [t for t in toks if isinstance(t, str) and t != ","]
    padded = " " + " ".join(words) + " "

    def has(intent):
        return any((" " + k) in padded if " " in k else any(hit(w, k) for w in words) for k in KW[intent])

    items = find_items(toks)
    out = khata_intents(has, words, toks, items)
    if out:
        pass
    elif has("checkout") and not items:
        out.append(("paid", {"t": checkout()}) if CART else ("empty", {}))
    elif has("clear") or (has("remove") and has("all") and not items):
        CART.clear()
        out.append(("cleared", {}))
    elif has("remove"):
        remove(items, out)
    elif items and has("price") and has("set") and items[0][1]:   # "chawal ka rate 65 karo"
        PRODUCTS[items[0][0]]["price"] = items[0][1]
        out.append(("price_set", {"pid": items[0][0]}))
    elif items and has("stockword") and has("add"):               # "rice stock 20 kilo add"
        for pid, q in items:
            if q:
                PRODUCTS[pid]["stock"] = round(PRODUCTS[pid]["stock"] + q, 3)
            out.append(("restocked", {"pid": pid}) if q else stock_msg(pid))
    elif items and has("price"):
        out += price_msgs(items)
    elif items and has("add"):
        add(items, out)
        if has("total"):
            out.append(total_msg())
    elif items and has("stock"):
        out += [stock_msg(p) for p, _ in items]
    elif items and has("howmuch"):
        out += price_msgs(items)
    elif has("sales"):
        s = today_summary()
        out.append(("sales", {"t": STATE["sales"], "b": STATE["bills"], "cash": s["cash"], "credit": s["credit"],
                              "got": s["collected"]}))
        if s["items"]:
            out.append(("sales_top", {"items": [(p, q) for p, q, _ in s["items"][:3]]}))
    elif has("stockword"):
        out.append(low_msg())
    elif has("total") or has("howmuch"):
        out.append(total_msg())
    elif has("stock"):
        out.append(low_msg())
    elif items and any(q for _, q in items):                       # "2 kilo biyyam" -> into the bill
        add(items, out)
    elif items:                                                    # just "biyyam" -> price and stock
        for pid, _ in items:
            out += [("price", {"pid": pid}), stock_msg(pid)]
    else:
        out.append((next((k for k in ("greet", "timing", "help", "thanks") if has(k)), "unknown"), {}))

    return reply(out, detect(raw, ui))


def reply(out, lang):
    return {"lang": lang, "reply": render(out, LANGS.index(lang)), "en": render(out, 0)}


def num(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


def rupees(x):
    return f"{x:.2f}".removesuffix(".00")


def render(msgs, li):
    parts = []
    for key, f in msgs:
        f = dict(f)
        if "pid" in f:
            p = PRODUCTS[f["pid"]]
            u = UNITS[p["unit"]][li]
            f.update(name=p["names"][li], u=u, p=rupees(p["price"]), s=f"{num(f.get('s', p['stock']))} {u}")
        if "items" in f:
            f["x"] = ", ".join(f"{num(q)} {UNITS[PRODUCTS[i]['unit']][li]} {PRODUCTS[i]['names'][li]}" for i, q in f["items"])
        if "q" in f:
            f["q"] = num(f["q"])
        for k in ("t", "amt", "due", "cash", "credit", "got"):
            if k in f:
                f[k] = rupees(f[k])
        parts.append(MSG[key][li].format(**f))
    return " ".join(parts)


# ---------------------------------------------------------------- storage + web server
def snapshot():
    return {
        "products": [{"id": p, "names": d["names"], "unit": UNITS[d["unit"]], "price": d["price"], "stock": d["stock"]}
                     for p, d in PRODUCTS.items()],
        "cart": [{"id": p, "qty": q, "amount": round(q * PRODUCTS[p]["price"], 2)} for p, q in CART.items()],
        "total": cart_total(), "sales": STATE["sales"], "bills": STATE["bills"], "low": LOW_STOCK, "today": today_summary(),
        # ponytail: only each customer's last 50 history lines go to the page (the file keeps all); page through if needed
        "khata": [{"name": e["name"], "due": e["due"], "history": e["history"][-50:]}
                  for e in sorted(KHATA.values(), key=lambda e: (-e["due"], e["name"]))],
    }


def new_day():
    today = date.today().isoformat()
    if STATE["day"] != today:
        STATE.update(day=today, sales=0.0, bills=0, today=[])


def save():
    data = {**STATE, "cart": CART, "khata": KHATA,
            "products": {p: {"price": d["price"], "stock": d["stock"]} for p, d in PRODUCTS.items()}}
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, DATA_FILE)                                   # never leaves a half-written file


def load():
    if not DATA_FILE.exists():
        return
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    for pid, d in data.get("products", {}).items():
        if pid in PRODUCTS:
            PRODUCTS[pid].update(price=float(d["price"]), stock=float(d["stock"]))
    CART.update({p: q for p, q in data.get("cart", {}).items() if p in PRODUCTS})
    for e in data.get("khata", {}).values():     # re-key by sound; files from before history have none
        entry = KHATA.setdefault(khata_key(e["name"]), {"name": e["name"], "due": 0.0, "history": []})
        entry["due"] = round(entry["due"] + e["due"], 2)
        entry["history"] += e.get("history", [])
    STATE.update({k: data[k] for k in ("day", "sales", "bills", "today") if k in data})
    new_day()


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            new_day()
            self.send(200, snapshot())
        else:
            self.send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            new_day()
            if self.path == "/api/chat":
                lang = body.get("lang") if body.get("lang") in LANGS else "en"
                result = respond(str(body.get("text", ""))[:500], lang)
            elif self.path == "/api/set":                        # price/stock typed into the table
                product, result = PRODUCTS[body["id"]], {}
                for k in ("price", "stock"):
                    if k in body:
                        v = float(body[k])
                        if not 0 <= v < 1e7:
                            raise ValueError(f"{k} must be between 0 and 1,00,00,000")
                        product[k] = v
            elif self.path == "/api/khata":                      # "Add to khata" / "Record payment" / "Delete"
                lang = body.get("lang") if body.get("lang") in LANGS else "en"
                name = " ".join(str(body.get("name", "")).split())[:40]
                if not name:
                    raise ValueError("type the customer's name")
                if ("pay" in body or body.get("delete")) and khata_key(name) not in KHATA:
                    raise ValueError(f"no khata for {name}")
                if body.get("delete"):
                    out = [delete_khata(khata_key(name))]
                elif "pay" in body:
                    amount = float(body["pay"])
                    if not 0 < amount < 1e7:
                        raise ValueError("amount must be more than 0")
                    out = [khata_pay(khata_key(name), amount)]
                else:
                    out = [to_khata(name) if CART else ("empty", {})]
                result = reply(out, lang)
            else:
                return self.send(404, {"error": "not found"})
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            return self.send(400, {"error": f"bad request: {e}"})
        save()
        self.send(200, {**result, "state": snapshot()})

    def log_message(self, *args):
        pass


# ---------------------------------------------------------------- self-check
def selftest():
    def items(text):
        return find_items(numbers(tokenize(text)))

    # numbers said in three languages
    assert items("rendunnara kilo biyyam") == [["rice", 2.5]]
    assert items("okatinnara kilo chakkera") == [["sugar", 1.5]]
    assert items("ढाई किलो चावल") == [["rice", 2.5]]
    assert items("dedh kilo aata aur 6 ande") == [["atta", 1.5], ["eggs", 6.0]]
    assert items("500 grams sugar") == [["sugar", 0.5]]
    assert items("అర కిలో కంది పప్పు, ఒక డజను గుడ్లు") == [["toordal", 0.5], ["eggs", 12.0]]
    assert items("twenty five eggs") == items("iravai aidu guddulu") == [["eggs", 25.0]]
    assert items("sava kilo chawal") == [["rice", 1.25]]
    assert items("one and a half kg rice") == [["rice", 1.5]]
    assert items("biyyam rendu kilo, chakkera oka kilo") == [["rice", 2.0], ["sugar", 1.0]]
    assert items("chawal de do") == [["rice", None]]              # "do" = give here, not 2
    assert items("do kilo chawal") == [["rice", 2.0]]

    # a full billing conversation
    r = respond("రెండు కిలోల బియ్యం వేయి")
    assert r["lang"] == "te" and CART == {"rice": 2}, r
    r = respond("चीनी का दाम क्या है")
    assert r["lang"] == "hi" and "48" in r["reply"], r
    respond("do kilo chawal dalo")
    assert CART == {"rice": 4}
    r = respond("Do you have milk?")
    assert r["lang"] == "en" and "24" in r["reply"] and "milk" not in CART, r
    respond("2 kg rice, 3 milk packets and 1 soap add")
    assert CART == {"rice": 6, "milk": 3, "soap": 1}
    respond("add 1 rice")
    assert list(CART) == ["rice", "milk", "soap"]                 # bill rows don't jump around
    respond("remove 1 rice")
    r = respond("total entha")
    assert r["lang"] == "te" and "485" in r["reply"], r
    respond("vaddu")                                              # undo last item
    assert "soap" not in CART
    respond("remove 1 milk")
    assert CART["milk"] == 2
    r = respond("add 1000 kg rice")
    assert CART["rice"] == 6 and "44" in r["reply"], r            # only 50 - 6 left
    respond("rice stock 20 kilo add")
    assert PRODUCTS["rice"]["stock"] == 70
    respond("chawal ka rate 65 karo")
    assert PRODUCTS["rice"]["price"] == 65
    respond("bill paid")
    assert not CART and PRODUCTS["rice"]["stock"] == 64 and STATE["sales"] == 6 * 65 + 2 * 30
    assert "450" in respond("ఈరోజు అమ్మకాలు")["reply"]
    assert "Bread" in respond("stock")["reply"]
    assert respond("blah blah")["reply"].startswith("Sorry")

    # khata (credit book)
    def due(name):
        return KHATA[phon(name)]["due"]

    respond("2 kg rice")
    r = respond("Ramesh khata lo rasko")                          # new customer, name picked out of the sentence
    assert not CART and KHATA[phon("Ramesh")]["name"] == "Ramesh" and due("Ramesh") == 130 and "Ramesh" in r["reply"], r
    respond("1 soap")
    respond("ramesh ke khate mein likho")                         # same customer, in Hindi
    assert due("Ramesh") == 165
    assert "165" in respond("ramesh baki entha")["reply"]
    assert "Ramesh ₹165" in respond("khata")["reply"]
    respond("Ramesh 100 ichhadu")                                 # part payment
    assert due("Ramesh") == 65
    respond("ramesh ne 65 diye")                                  # settled, history kept
    hist = KHATA[phon("Ramesh")]["history"]
    assert due("Ramesh") == 0 and [h["amount"] for h in hist] == [130, 35, -100, -65] and hist[0]["items"] == [["rice", 2.0]]
    assert hist[-1]["balance"] == 0 and hist[-1]["at"][:10] == date.today().isoformat()
    assert respond("udhaar kitna hai")["reply"] == MSG["khata_none"][2]    # "hai" is not a customer
    respond("1 soap")
    r = respond("khata lo rasko")                                 # no name given -> ask, keep the bill
    assert CART == {"soap": 1} and r["reply"] == MSG["khata_who"][1], r
    respond("clear")

    # voice payments: names in another script or spelling, glued suffixes, "2,000"
    assert phon("Ramesh") == phon("రమేష్") == phon("रमेश") and phon("Lakshmi") == phon("Laxmi") == phon("లక్ష్మీ") == phon("लक्ष्मी")
    assert phon("Krishna") == phon("కృష్ణ") and phon("Sai") == phon("సాయి") and phon("Yashwanth") == phon("యశ్వంత్") == phon("Yashwant")
    respond("3 kg rice")
    respond("customer name Lakshmi khata lo rasko")               # "customer name" is not part of the name
    assert KHATA[phon("Lakshmi")]["name"] == "Lakshmi" and due("Lakshmi") == 195
    respond("లక్ష్మి 100 రూపాయలు ఇచ్చింది")                        # khata typed in English, paid in Telugu
    assert due("Lakshmi") == 95
    respond("लक्ष्मी जी से 50 मिले")                                  # and in Hindi
    assert due("Lakshmi") == 45
    respond("లక్ష్మిగారు 2,000 ఇచ్చారు")                              # glued "garu"; 2,000 is two thousand -> settles 45
    assert due("Lakshmi") == 0
    # money safety: a similar name is a different person, and an unknown payer never closes the open bill
    respond("2 kg rice")
    r = respond("Rakesh 100 ichhadu")
    assert CART == {"rice": 2} and "Rakesh" in r["reply"] and phon("Rakesh") not in KHATA, r
    respond("Sai Kumar khata lo rasko")
    respond("1 soap")
    respond("Sai Ram khata lo rasko")                             # shares a first name, still a new customer
    assert due("Sai Kumar") == 130 and due("Sai Ram") == 35
    r = respond("Sai 20 ichhadu")                                 # ambiguous -> ask, change nothing
    assert "Sai Kumar" in r["reply"] and "Sai Ram" in r["reply"] and due("Sai Kumar") == 130 and due("Sai Ram") == 35

    # today's sales details: cash vs khata, khata payments, items sold
    s = today_summary()
    assert (s["cash"], s["credit"], s["collected"], s["earlier"]) == (450, 525, 360, 0), s
    assert s["cash"] + s["credit"] == STATE["sales"] and sum(a for _, _, a in s["items"]) == STATE["sales"]
    assert s["items"][0] == ["rice", 13.0, 845.0], s["items"]                 # 6 + 2 + 3 + 2 kg at ₹65
    r = respond("today sales")
    assert "cash ₹450" in r["reply"] and "on khata ₹525" in r["reply"] and "13 kg Rice" in r["reply"], r
    # deleting a customer removes their khata but not today's sales lines
    assert delete_khata(phon("Sai Ram"))[0] == "khata_deleted" and phon("Sai Ram") not in KHATA
    assert today_summary()["credit"] == 525
    print("self-check passed")


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        selftest()
    else:
        load()
        url = f"http://127.0.0.1:{PORT}/"
        try:
            server = HTTPServer(("127.0.0.1", PORT), Handler)
        except OSError:
            sys.exit(f"Port {PORT} is busy - the assistant is probably already running in another window. Open {url}")
        print(f"Kirana assistant running at {url}\nKeep this window open while you use it. Press Ctrl+C to stop.")
        if "--no-browser" not in sys.argv:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")
