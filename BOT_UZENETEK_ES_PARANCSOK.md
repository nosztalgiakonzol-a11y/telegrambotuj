# GoldenTipsHungary bot – üzenetek és parancsok

## Telegram parancsok

- `/start`
- `/irodak`
- `/help`
- `/kancelarije`
- `/pomoc`

## Felhasználónak küldött chat üzenetek

### 1) Indulás / aktiváció

- `👋 <b>Üdvözlünk a GoldenTipsHungary rendszerében!</b>` + aktivációs kód bekérése.
- `Először aktiváld a fiókodat a /start paranccsal.`
- Útmutató ajánló szöveg (`📘 ...`) sikeres aktiváció után.
- Hibás kód esetén:
  - `❌ <b>GoldenTipsHungary</b>`
  - `Hibás aktivációs kód.`
  - `Próbáld újra (teszt kód: <b>123</b>).` / `Pokušaj ponovo (test kod: <b>123</b>).`
- Állapot-specifikus figyelmeztetések:
  - útmutató visszaigazolás hiánya
  - irodaválasztásra felszólítás
  - `/start` újrakezdésre felszólítás

### 2) Irodaválasztás képernyő (`selection_text`)

- Fejléc:
  - `✅ <b>GoldenTipsHungary</b> • Aktiváció sikeres`
  - vagy `⚙️ <b>GoldenTipsHungary</b> • Szűrők módosítása`
- Törzs:
  - irodaválasztási útmutató (max 6)
  - regisztrációs link
  - útmutató link
  - kiválasztott irodák listája / `Még semmit nem választottál.`

### 3) Útmutató visszaigazolás

- `✅ Útmutató visszaigazolva.`

### 4) Irodák mentése után

- Mentés-visszaigazolás + `/irodak` módosítás infó + útmutató link +
  `Küldöm a jelenleg aktív fogadásokat...`

### 5) Aktív arbitrázs üzenet (dinamikus)

Template:

- `🔒 <b>ÚJ ARBITRÁZS FOGADÁS</b>`
- `💸 Profit`, `🟢 STÁTUSZ: AKTÍV`, `📅 Dátum`
- Bookmaker 1 blokk: név/link, mérkőzés, fogadás, odds
- Bookmaker 2 blokk: név/link, mérkőzés, fogadás, odds
- `⚙️ Szűrő módosítás: /irodak`

### 6) /help

- Parancslista szöveg:
  - `/start - GoldenTipsHungary flow indítása`
  - `/irodak - szűrt irodák módosítása`
  - `/help - segítség`

## Callback válaszok (toast / alert)

- `Először /start és aktivációs kód szükséges.`
- `Szuper! Jöhetnek a kiválasztott irodák ✅`
- `Szűrőmódosítás megnyitva ⚙️`
- `Ismeretlen iroda.`
- `Eltávolítva ✅`
- `Hozzáadva ✅`
- `Maximum 6 irodát választhatsz.`
- `Válassz legalább 2 irodát az arbitrázshoz.`
- `GoldenTipsHungary tipp érkezik 🚀` / `GoldenTipsHungary tip stiže 🚀`
- `Ismeretlen művelet.`

## Inline gombfeliratok

- Bookmaker választó gombok: `{emoji} {bookmaker_name}` (kijelölve: `✅ ...`)
- `💰 Nincs fiókod? Regisztrálj`
- `✅ Kész`
- `📘 Útmutató megnyitása`
- `✅ Okés, elolvastam az útmutatót`
- Aktív bet üzenet gombok:
  - `{bookmaker1_name}`
  - `{bookmaker2_name}`
  - `🧮 Kalkulátor`
  - `💰 Nincs fiókod? Regisztrálj`

---

> Megjegyzés: a `{...}` jelölések dinamikus mezők (adatbázis/config alapján).


## Szerb fordítások

A bot fő felhasználói üzenetei kétnyelvűek lettek (magyar + szerb), azonos jelentéssel.
