# Travel Inn — Which Pilot Question Bank Questions the Data Can Actually Answer

**Date:** 17 Aug 2026
**Coverage:** **All 52 files read.** 15 PDFs in full text; **all 37 image files** read section by section.
**Standard:** Judged against the data **as it exists today**. Every answer is traceable to a named file and a named section — nothing inferred from outside the client's data.
**Question text:** Reproduced **verbatim** from *Property AI Chatbot — Pilot Question Bank*. No rewording.

---

## How to read the tables

**Tier 1 vs Tier 2** — Tier 1 is backed by a *structured field* present in nearly every file, so the answer is a lookup and will be consistent. Tier 2 is *prose* — reliably present, but written as sentences, so the answer depends on the model reading and summarising rather than retrieving a value.

| Type | Meaning | What it tests |
|---|---|---|
| **[P]** | Needs a property name filled into the `[Property Name]` placeholder before it can be asked | Finding the right document and reading it |
| **[C]** | Searches across all 52 properties as written | Filtering and comparing across the whole set |

Only **5 of the 30** are **[C]**. Those five are the harder half — they break on plain vector search and need the structured property table.

---

## Tier 1 — structured field, near-total coverage

| # | Bank section | Question (verbatim) | Type | Verify in this file | Section | Actual value |
|---|---|---|---|---|---|---|
| 1 | 2. Location & Accessibility | What is the nearest airport to [Property Name], and approximately how far is it from the property? | **[P]** | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` | QUICK FACTS | Jabalpur 203 km; Khajuraho 226 km |
| 2 | 2. Location & Accessibility | How long does the road journey from the nearest airport to [Property Name] take? | **[P]** | same file | QUICK FACTS | Jabalpur 3.5 hrs; Khajuraho 5 hours |
| 3 | 2. Location & Accessibility | Are there multiple airport options for reaching [Property Name]? If so, compare them in terms of distance and driving time. | **[P]** | `Kerala\Wayanad\Vayal Veedu Product Update.jpeg` | QUICK FACTS | Mysore 107 km / 2.5 hrs; Calicut 118 km / 3 hrs; Kannur 114 km / 3 hrs |
| 4 | 2. Location & Accessibility | What is the nearest railway station to [Property Name]? | **[P]** | `West Bengal\Siliguri\Courtyard Siliguri Property Update (1).png` | QUICK FACTS | Siliguri Junction; New Jalpaiguri Junction |
| 5 | 2. Location & Accessibility | How far is the nearest railway station from the property, and how long does the transfer take? | **[P]** | same file | QUICK FACTS | Siliguri Jn 1 km / 6 mins; NJP 7 km / 30 mins |
| 6 | 3. Safari & Wildlife Logistics | Which safari gate is closest to [Property Name], and how long does it take to reach the gate? | **[P]** | `Uttar Pradesh\Dudhwa\Camp Tiger Lily Property Update.png` | QUICK FACTS | Kishanpur Gate — 2 km / 5 mins |
| 7 | 3. Safari & Wildlife Logistics | What is the best time of year to stay at [Property Name] for wildlife viewing? | **[P]** | `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png` | QUICK FACTS | Oct – Feb |
| 8 | 1. Property Overview | How many keys does [Property Name] have, and what are the different room or accommodation categories? | **[P]** | same file | INVENTORY SIZE | 20 Rooms / 03 Categories — Planter's Den 4, Tamarind Canopy Luxe Cabins 8, Luxury Machaans 8 |
| 9 | 11. Quick Search | Which properties have fewer than 20 rooms? | **[C]** | corpus-wide | QUICK FACTS → Accommodations | Kathoni 2, Agoratoli 3, Haldu Tola 4, Varenya Life 4, Postcard Leh 5, Camp TigerLily 6, Kinwani 6, Dolkhar 7, Kaav 7, Outpost 12 9, Bagh Tola 10, Sitara 10, Cabo Serai 11, Vayal Veedu 10, Jaagir 13, Guleria Kothi 15, Rambha 16, Saj in the Forest 17, Utsav Camp 18, The Nanee 18 |
| 10 | 11. Quick Search | Which properties are closest to the airport? | **[C]** | corpus-wide | QUICK FACTS | Dolkhar Ladakh — Leh 4.3 km / 15 mins; Courtyard Siliguri — Bagdogra 14 km / 31 mins; Postcard Leh — 14 km / 25 mins |
| 11 | 11. Quick Search | Which properties are closest to the safari gate? | **[C]** | corpus-wide | QUICK FACTS | Camp TigerLily — Kishanpur 2 km / 5 mins; Bagh Tola — Khitauli 5 km / 15 mins; Utsav Camp — Tehla 7 km |
| 12 | 1. Property Overview | Where exactly is [Property Name] located, and which national park, wildlife reserve or destination is it associated with? | **[P]** | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` | QUICK FACTS → Location | Kaziranga National Park, Assam |
| 13 | 3. Safari & Wildlife Logistics | Which national park, tiger reserve or wildlife area is [Property Name] closest to? | **[P]** | `Madhya Pradesh\Pench\Haldu Tola Property Update.png` | QUICK FACTS | Near Pench Tiger Reserve; Closest Entry Gate: Karmajhiri Gate |
| 14 | 1. Property Overview | Is [Property Name] a large resort, a boutique lodge, a small luxury camp or an intimate property? | **[P]** | same file | INTRODUCTION + INVENTORY SIZE | "exclusive luxury safari retreat"; "The property has only four rooms" |
| 15 | 6. Food & Dietary Requirements | Are meals included in the standard room rate, and what meal plan options are available? | **[P]** | multiple | PRICE RANGE | Agoratoli ₹9,250 (MAP); Bagh Tola ₹24,000 (APAI); Jaagir Manor ₹35,000 (EPAI); Rambha Palace ₹41,500 (CPAI) |

## Tier 2 — prose, consistently present

| # | Bank section | Question (verbatim) | Type | Verify in this file | Section | Actual value |
|---|---|---|---|---|---|---|
| 16 | 1. Property Overview | Tell me about [Property Name]. What kind of property is it and what is the overall experience it offers? | **[P]** | any image file | INTRODUCTION + LOOK & FEEL | Kaav — "A compact luxury lodge with forest-facing rooms and tents" |
| 17 | 1. Property Overview | What makes [Property Name] different from other properties in the same destination? | **[P]** | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` | WHY CHOOSE KAAV? | "Assured safari seat allocation: 2 seats for morning and 4 for afternoon safaris" |
| 18 | 1. Property Overview | What are the main selling points of [Property Name] that our sales team should highlight to an international client? | **[P]** | same file | WHY CHOOSE + PROS OF STAYING AT KAAV | 5 bullets |
| 19 | 10. Sales-Recommendation | Give me the top five selling points of [Property Name] that I can use when presenting it to an overseas travel partner. | **[P]** | same file | WHY CHOOSE KAAV? | 5 bullets as written |
| 20 | 7. Families, Seniors & Client Profiles | Would this property work well for wildlife enthusiasts, photographers or serious birdwatchers? | **[P]** | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` | IDEAL FOR | Wildlife Enthusiasts; Birders and Photographers; Nature Immersion Travellers |
| 21 | 11. Quick Search | Which properties are good for families? | **[C]** | corpus-wide | IDEAL FOR | Agoratoli "Birdwatchers, families, and small groups"; Vythiri "Nature and Wellness Travellers, Families, Birdwatchers" |
| 22 | 4. Activities & Experiences | What activities can guests do at [Property Name] apart from safari? | **[P]** | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` | EXPERIENCES & ACTIVITIES | 9 items incl. village walks, Misingi tribal interaction, e-auto rides, cycling, 60 ft waterfall walk |
| 23 | 3. Safari & Wildlife Logistics | Does the property offer walking safaris, nature walks, birding, boat safaris, cycling or other outdoor activities? | **[P]** | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` | EXPERIENCES + SAFARI INFORMATION | Nature Walk; Birding (~300 species); Kayaking; land **and boat** safaris |
| 24 | 4. Activities & Experiences | Does [Property Name] offer cultural, village or community-based experiences? | **[P]** | `Assam\Kaziranga\Kathoni Property Update.png` | OTHER EXPERIENCES AT THE PROPERTY | Village Visit; Cooking Sessions; Traditional Bihu Song & Dance by the community |
| 25 | 3. Safari & Wildlife Logistics | What wildlife can guests realistically expect to see in the area around [Property Name]? | **[P]** | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` | WHY CHOOSE | "Big 5 sightings (Rhino, Tiger, Buffalo, Elephant, Swamp Deer)"; ~70% of Kaziranga's 350 bird species |
| 26 | 3. Safari & Wildlife Logistics | Are trained naturalists or guides provided with the safari? | **[P]** | `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png` | PROS OF STAYING AT MACHAAN | "Team of 4 skilled naturalists with good English communication" |
| 27 | 8. Responsible Tourism & Conservation | What conservation initiatives does [Property Name] support? | **[P]** | `Nepal\Red Panda Outpost Property Update.png` | INTRODUCTION + WHY CHOOSE | Community-led conservation initiative; scientific tracking support; trained red panda trackers |
| 28 | 8. Responsible Tourism & Conservation | Which properties in our database have the strongest conservation or community engagement programmes? | **[C]** | corpus-wide | WHY CHOOSE / PROS | Dolkhar zero-waste & zero-plastic, 40+ Ladakhi artisans; Agoratoli eco-certified; Red Panda Outpost; Sariska Lodge 15 acres afforested |
| 29 | 10. Sales-Recommendation | Compare [Property A] and [Property B] for a luxury international client. Include location, accessibility, accommodation, safari, activities, facilities, food and overall experience. | **[P]** | any two image files | all sections | All eight requested dimensions present in both |
| 30 | 10. Sales-Recommendation | What type of client would you NOT recommend [Property Name] to, and why? | **[P]** | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` | TRAVEL INN RECOMMENDS | "The base category tents are not recommended, as their compact room and bathroom size may not meet the expectations of comfort-focused travellers." |

**Why #30 matters:** the data contains real negative guidance, not just marketing. That is what makes a sales team trust the tool.

---

## Will fail — no data at all

Roughly **60 questions**.

| Area | Bank section |
|---|---|
| Wi-Fi, mobile network, connectivity | 5 |
| Card payments, foreign currency, currency exchange, tipping box | 5 |
| Electrical sockets, USB ports, adapters, backup generator | 5 |
| Equipment rental — cameras, binoculars, laptops | 5 |
| Maximum guest capacity, extra beds, tour leader / escort room | 1, 5 |
| Medical assistance, distance to hospital | 1, 2 |
| Transfers arranged by the property | 2 |
| Laundry, in-room dining, gym | 5 |
| Senior travellers, mobility / accessibility, child age limits | 7 |
| Park closure periods and alternatives | 4 |
| Holi / Diwali dates, festivals, seasonal closures | 12 |
| Safari zones, buffer zones, zone-by-zone wildlife | 12 |
| Park-level features — landscape, habitat, flora, fauna | 12 |
| Full-day / half-day safari options | 12 |
| Source-market preferences — UK, USA, Europe, Australia | 12 |
| Recurring complaints, negative feedback, service issues | 12 |
| Packed breakfasts/meals, special safari meal timings | 6 |

Two of those clusters are **park-level, not property-level** — safari zones, and park features. No amount of ingesting property sheets produces them; they need a separate destination dataset.

---

## What to tell the client

**Roughly 55–65 of the bank are answerable today.** The 30 above are the strongest and should form the acceptance test.
