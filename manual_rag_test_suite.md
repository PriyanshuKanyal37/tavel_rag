# Travel Inn Sales Knowledge Assistant — Manual RAG Test Suite (Top 30 Questions)

This test suite contains the **Top 30 verified test questions** selected from the client's question bank (`AI Chatbot Questions.docx` and `valid_q.md`), with all placeholders populated with real properties from the raw dataset (`data/raw/Property Updates`). Every question has a confirmed ground-truth answer directly traceable to the raw property sheets.

Use this document to manually test your RAG system:
1. **Copy** the exact question prompt into the chat UI (`http://127.0.0.1:5173/`).
2. **Compare** the assistant's output against the **Expected Ground Truth Answer**.
3. **Verify** that the cited source matches the **Source Document & Section**.

---

## Quick Reference Summary Table

| # | Category | Exact Test Question | Target Property / Scope | Primary Source File |
|---|---|---|---|---|
| **1** | Property Overview | *Tell me about KAAV Safari Lodge. What kind of property is it and what is the overall experience it offers?* | KAAV Safari Lodge | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` |
| **2** | Property Overview | *Where exactly is Agoratoli Jungalow located, and which national park, wildlife reserve or destination is it associated with?* | Agoratoli Jungalow | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` |
| **3** | Property Overview | *Is Haldu Tola a large resort, a boutique lodge, a small luxury camp or an intimate property?* | Haldu Tola | `Madhya Pradesh\Pench\Haldu Tola Property Update.png` |
| **4** | Property Overview | *How many keys does Machaan Wilderness Lodge have, and what are the different room or accommodation categories?* | Machaan Wilderness Lodge | `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png` |
| **5** | Property Overview | *What makes KAAV Safari Lodge different from other properties in the same destination?* | KAAV Safari Lodge | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` |
| **6** | Property Overview | *What are the main selling points of KAAV Safari Lodge that our sales team should highlight to an international client?* | KAAV Safari Lodge | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` |
| **7** | Location & Access | *What is the nearest airport to Bagh Tola, and approximately how far is it from the property?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |
| **8** | Location & Access | *How long does the road journey from the nearest airport to Bagh Tola take?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |
| **9** | Location & Access | *Are there multiple airport options for reaching Vayal Veedu? If so, compare them in terms of distance and driving time.* | Vayal Veedu | `Kerala\Wayanad\Vayal Veedu Product Update.jpeg` |
| **10** | Location & Access | *What is the nearest railway station to Courtyard by Marriott Siliguri?* | Courtyard Siliguri | `West Bengal\Siliguri\Courtyard Siliguri Property Update (1).png` |
| **11** | Location & Access | *How far is the nearest railway station from Courtyard by Marriott Siliguri, and how long does the transfer take?* | Courtyard Siliguri | `West Bengal\Siliguri\Courtyard Siliguri Property Update (1).png` |
| **12** | Safari Logistics | *Which national park, tiger reserve or wildlife area is Haldu Tola closest to?* | Haldu Tola | `Madhya Pradesh\Pench\Haldu Tola Property Update.png` |
| **13** | Safari Logistics | *Which safari gate is closest to Camp Tiger Lily, and how long does it take to reach the gate?* | Camp Tiger Lily | `Uttar Pradesh\Dudhwa\Camp Tiger Lily Property Update.png` |
| **14** | Safari Logistics | *What is the best time of year to stay at Machaan Wilderness Lodge for wildlife viewing?* | Machaan Wilderness Lodge | `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png` |
| **15** | Safari Logistics | *Does KAAV Safari Lodge offer walking safaris, nature walks, birding, boat safaris, cycling or other outdoor activities?* | KAAV Safari Lodge | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` |
| **16** | Safari Logistics | *What wildlife can guests realistically expect to see in the area around Agoratoli Jungalow?* | Agoratoli Jungalow | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` |
| **17** | Safari Logistics | *Are trained naturalists or guides provided with the safari at Machaan Wilderness Lodge?* | Machaan Wilderness Lodge | `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png` |
| **18** | Activities & Experiences | *What activities can guests do at Agoratoli Jungalow apart from safari?* | Agoratoli Jungalow | `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png` |
| **19** | Activities & Experiences | *Does Kathoni offer cultural, village or community-based experiences?* | Kathoni | `Assam\Kaziranga\Kathoni Property Update.png` |
| **20** | Food & Rates | *Are meals included in the standard room rate, and what meal plan options are available at Bagh Tola?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |
| **21** | Client Profiles | *Would Bagh Tola work well for wildlife enthusiasts, photographers or serious birdwatchers?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |
| **22** | Conservation | *What conservation initiatives does Red Panda Outpost support?* | Red Panda Outpost | `Nepal\Red Panda Outpost Property Update.png` |
| **23** | Conservation | *Which properties in our database have the strongest conservation or community engagement programmes?* | Corpus-wide | Multiple (`Dolkhar`, `Red Panda`, `Agoratoli`, `Sariska Lodge`) |
| **24** | Sales Recommendation | *Give me the top five selling points of KAAV Safari Lodge that I can use when presenting it to an overseas travel partner.* | KAAV Safari Lodge | `Karnataka\Kabini\Kaav Safari Lodge Property Update.png` |
| **25** | Sales Recommendation | *Compare KAAV Safari Lodge and Bagh Tola for a luxury international client. Include location, accessibility, accommodation, safari, activities, facilities, food and overall experience.* | KAAV vs Bagh Tola | `Kabini\Kaav Safari Lodge...` & `Bandhavgarh\Bagh Tola...` |
| **26** | Sales Recommendation | *What type of client would you NOT recommend Bagh Tola to, and why?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |
| **27** | Quick Search | *Which properties have fewer than 20 rooms?* | Corpus-wide (SQL / Filter) | Portfolio-wide inventory |
| **28** | Quick Search | *Which properties are closest to the airport?* | Corpus-wide (SQL / Filter) | Portfolio-wide distance |
| **29** | Quick Search | *Which properties are closest to the safari gate?* | Corpus-wide (SQL / Filter) | Portfolio-wide gate proximity |
| **30** | Quick Search | *Which properties are good for families?* | Corpus-wide (Tag / Filter) | Portfolio-wide tags |
| **31** | *Boundary Test (I Don't Know)* | *What is Taj Mahal, New Delhi's official star rating?* | Taj Mahal New Delhi | `Delhi\Taj Mahal Delhi Property Update.png` |
| **32** | *Boundary Test (I Don't Know)* | *Does Bagh Tola accept cash payment in foreign currencies such as USD or GBP?* | Bagh Tola | `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png` |

---

## Detailed Test Cases & Ground Truth Answers

---

### Category 1: Property Overview & Basic Information

#### Question 1
- **Exact Copy-Paste Prompt:**
  ```text
  Tell me about KAAV Safari Lodge. What kind of property is it and what is the overall experience it offers?
  ```
- **Source Document:** `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
- **Section:** `INTRODUCTION`, `LOOK & FEEL`, `QUICK FACTS`
- **Expected Ground Truth Answer:**
  KAAV Safari Lodge is an intimate, boutique luxury wilderness lodge situated on the southern fringe of Nagarhole National Park (Kabini), Karnataka. It offers an exclusive, low-density wildlife experience with just 7 keys: 4 Superior Rooms (450 sq.ft), 2 Luxury Tents (450 sq.ft), and 1 private Pool Villa (930 sq.ft). The architecture uses modern design with natural materials that blend with the forest canopy. The overall experience emphasizes privacy, quiet immersion, alfresco dining with personalized timings, swimming pool relaxation, and dual wildlife exploration on both land (Nagarhole jeep safaris) and water (Kabini River boat safaris, coracle rides, and kayaking).
- **Verification Criteria:** Must identify Kabini/Nagarhole location, compact luxury scale (7 keys), and both land and river safari experiences.

---

#### Question 2
- **Exact Copy-Paste Prompt:**
  ```text
  Where exactly is Agoratoli Jungalow located, and which national park, wildlife reserve or destination is it associated with?
  ```
- **Source Document:** `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png`
- **Section:** `QUICK FACTS`, `INTRODUCTION`
- **Expected Ground Truth Answer:**
  Agoratoli Jungalow is located in Kaziranga National Park in Assam. It is set across a 5-acre estate surrounded by tea gardens, rice fields, and fish ponds. Geographically, it is situated just 2 minutes away from the Eastern (Agoratoli) Zone and approximately 20–25 minutes from the Central Zone of Kaziranga.
- **Verification Criteria:** Must name Kaziranga National Park (Assam) and specifically mention the Agoratoli / Eastern Range (2 minutes away).

---

#### Question 3
- **Exact Copy-Paste Prompt:**
  ```text
  Is Haldu Tola a large resort, a boutique lodge, a small luxury camp or an intimate property?
  ```
- **Source Document:** `Madhya Pradesh\Pench\Haldu Tola Property Update.png`
- **Section:** `INTRODUCTION`, `INVENTORY SIZE`, `WHY CHOOSE HALDU TOLA?`
- **Expected Ground Truth Answer:**
  Haldu Tola is an exclusive, highly intimate luxury safari retreat—not a large resort. It has only **4 rooms**, ensuring an intimate, private setting with personalized service and minimal tourist footfall near Pench Tiger Reserve.
- **Verification Criteria:** Must state that it is an intimate / exclusive boutique retreat with exactly 4 rooms.

---

#### Question 4
- **Exact Copy-Paste Prompt:**
  ```text
  How many keys does Machaan Wilderness Lodge have, and what are the different room or accommodation categories?
  ```
- **Source Document:** `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png`
- **Section:** `INVENTORY SIZE`
- **Expected Ground Truth Answer:**
  Machaan Wilderness Lodge has **20 rooms (keys)** divided across **3 accommodation categories**:
  1. **Planter's Den**: 4 units
  2. **Tamarind Canopy Luxe Cabins**: 8 units
  3. **Luxury Machaans**: 8 units (features an outdoor bubble jet Jacuzzi)
- **Verification Criteria:** Must provide the exact count of 20 rooms and list all 3 categories (4 Planter's Den, 8 Tamarind Canopy, 8 Luxury Machaans).

---

#### Question 5
- **Exact Copy-Paste Prompt:**
  ```text
  What makes KAAV Safari Lodge different from other properties in the same destination?
  ```
- **Source Document:** `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
- **Section:** `WHY CHOOSE KAAV?`, `PROS OF STAYING AT KAAV`
- **Expected Ground Truth Answer:**
  Key differentiators of KAAV Safari Lodge in Kabini include:
  1. **Assured Safari Seat Allocation:** Direct allocation under the forest department quota: **2 seats for morning safaris and 4 seats for afternoon safaris**, a major advantage in high-demand Kabini.
  2. **Dual Land and Water Safari Access:** Offers both conventional jeep safaris in Nagarhole and boat safaris / river cruises on the Kabini River.
  3. **High Exclusivity:** Low inventory of just 7 keys avoids the high-volume crowds of larger Kabini resorts.
  4. **Active Water & Nature Experiences:** On-site kayaking on the Kabini reservoir, traditional coracle rides, and guided birding (~300 species).
- **Verification Criteria:** Must mention the assured safari seat allocation (2 morning / 4 afternoon) and the dual land/boat safari access.

---

#### Question 6
- **Exact Copy-Paste Prompt:**
  ```text
  What are the main selling points of KAAV Safari Lodge that our sales team should highlight to an international client?
  ```
- **Source Document:** `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
- **Section:** `WHY CHOOSE KAAV?`, `PROS OF STAYING AT KAAV`
- **Expected Ground Truth Answer:**
  The top selling points for an international client are:
  1. **Guaranteed Safari Access:** Assured quota of 2 morning and 4 afternoon safari seats.
  2. **Direct Jungle Proximity:** Overlooks Nagarhole Wildlife Sanctuary with close proximity to the safari entrance gate.
  3. **Diverse Wildlife Activities:** Both land jeeps and Kabini River boat cruises, plus kayaking, coracle rides, and nature walks.
  4. **Boutique Luxury & Privacy:** Only 7 keys (including luxury tents and a private pool villa) with attentive, personalized hosting.
  5. **Top-Tier Guiding:** Experienced in-house naturalists guiding wildlife walks and birdwatching (~300 bird species).
- **Verification Criteria:** Must cover guaranteed safari seats, small room count, land + boat safaris, and experienced naturalists.

---

### Category 2: Location & Accessibility

#### Question 7
- **Exact Copy-Paste Prompt:**
  ```text
  What is the nearest airport to Bagh Tola, and approximately how far is it from the property?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The nearest airport to Bagh Tola is **Jabalpur Airport**, located approximately **203 km** away. (Khajuraho Airport is an alternate option at approximately 226 km).
- **Verification Criteria:** Must cite Jabalpur Airport and the ~203 km distance.

---

#### Question 8
- **Exact Copy-Paste Prompt:**
  ```text
  How long does the road journey from the nearest airport to Bagh Tola take?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The road journey from Jabalpur Airport (the nearest airport, ~203 km) takes approximately **3.5 hours**. (If arriving via Khajuraho Airport at ~226 km, the road transfer takes approx. 5 hours).
- **Verification Criteria:** Must state ~3.5 hours from Jabalpur.

---

#### Question 9
- **Exact Copy-Paste Prompt:**
  ```text
  Are there multiple airport options for reaching Vayal Veedu? If so, compare them in terms of distance and driving time.
  ```
- **Source Document:** `Kerala\Wayanad\Vayal Veedu Product Update.jpeg`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  Yes, there are three airport options for reaching Vayal Veedu (Wayanad):
  1. **Mysore Airport:** Approx. **107 km | 2.5 hours** (closest and shortest drive)
  2. **Kannur International Airport:** Approx. **114 km | 3 hours**
  3. **Calicut International Airport (Kozhikode):** Approx. **118 km | 3 hours**
  Mysore is the recommended option for minimal road travel time.
- **Verification Criteria:** Must list all 3 airports with their respective distances (107 km, 114 km, 118 km) and times (2.5 hrs vs 3 hrs).

---

#### Question 10
- **Exact Copy-Paste Prompt:**
  ```text
  What is the nearest railway station to Courtyard by Marriott Siliguri?
  ```
- **Source Document:** `West Bengal\Siliguri\Courtyard Siliguri Property Update (1).png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The nearest railway station is **Siliguri Junction** (approx. 1 km away). The major regional junction, **New Jalpaiguri Junction (NJP)**, is located approx. 7 km away.
- **Verification Criteria:** Must mention Siliguri Junction (1 km) and NJP (7 km).

---

#### Question 11
- **Exact Copy-Paste Prompt:**
  ```text
  How far is the nearest railway station from Courtyard by Marriott Siliguri, and how long does the transfer take?
  ```
- **Source Document:** `West Bengal\Siliguri\Courtyard Siliguri Property Update (1).png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The nearest railhead, **Siliguri Junction**, is approximately **1 km** from the hotel, and the transfer takes only **6 minutes**. Alternatively, **New Jalpaiguri Junction (NJP)** is **7 km** away and takes approximately **30 minutes**.
- **Verification Criteria:** Must state 1 km / 6 mins for Siliguri Junction (and optionally 7 km / 30 mins for NJP).

---

### Category 3: Safari & Wildlife Logistics

#### Question 12
- **Exact Copy-Paste Prompt:**
  ```text
  Which national park, tiger reserve or wildlife area is Haldu Tola closest to?
  ```
- **Source Document:** `Madhya Pradesh\Pench\Haldu Tola Property Update.png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  Haldu Tola is located closest to **Pench Tiger Reserve** (Madhya Pradesh). Its closest entry point is the **Karmajhiri Gate**.
- **Verification Criteria:** Must identify Pench Tiger Reserve and Karmajhiri Gate.

---

#### Question 13
- **Exact Copy-Paste Prompt:**
  ```text
  Which safari gate is closest to Camp Tiger Lily, and how long does it take to reach the gate?
  ```
- **Source Document:** `Uttar Pradesh\Dudhwa\Camp Tiger Lily Property Update.png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The closest safari gate is **Kishanpur Gate** (Kishanpur Wildlife Sanctuary, Dudhwa Tiger Reserve), located **2 km** away, taking approximately **5 minutes**.
- **Verification Criteria:** Must specify Kishanpur Gate, 2 km, and 5 minutes.

---

#### Question 14
- **Exact Copy-Paste Prompt:**
  ```text
  What is the best time of year to stay at Machaan Wilderness Lodge for wildlife viewing?
  ```
- **Source Document:** `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png`
- **Section:** `QUICK FACTS`
- **Expected Ground Truth Answer:**
  The best time to stay at Machaan Wilderness Lodge for wildlife viewing is from **October to February (Oct – Feb)**.
- **Verification Criteria:** Must state October to February.

---

#### Question 15
- **Exact Copy-Paste Prompt:**
  ```text
  Does KAAV Safari Lodge offer walking safaris, nature walks, birding, boat safaris, cycling or other outdoor activities?
  ```
- **Source Document:** `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
- **Section:** `EXPERIENCES & ACTIVITIES`
- **Expected Ground Truth Answer:**
  Yes. KAAV Safari Lodge offers:
  - **Boat Safaris:** River cruises on the Kabini River between Nagarhole and Bandipur parks to view marsh crocodiles and water birds.
  - **Coracle Rides:** Traditional circular boat rides along the river's edge.
  - **Kayaking:** Paddling through the Kabini reservoir.
  - **Nature Walks:** Guided walks along the park periphery and reservoir banks.
  - **Birding:** Guided birdwatching spotting ~300 species (including Malabar Pied Hornbill and Nilgiri Flycatcher).
  - **Cycling:** Countryside cycling on lodge bicycles to explore local villages and scenery.
  - **Jungle Safaris:** Jeep safaris in Nagarhole National Park.
- **Verification Criteria:** Must confirm boat safaris, coracle rides, kayaking, nature walks, cycling, and birding.

---

#### Question 16
- **Exact Copy-Paste Prompt:**
  ```text
  What wildlife can guests realistically expect to see in the area around Agoratoli Jungalow?
  ```
- **Source Document:** `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png`
- **Section:** `WHY CHOOSE AGORATOLI JUNGALOW`
- **Expected Ground Truth Answer:**
  In the Agoratoli / Eastern range of Kaziranga, guests can realistically expect:
  - **Kaziranga's "Big 5":** Greater One-Horned Rhinoceros, Royal Bengal Tiger, Asian Elephant, Wild Water Buffalo, and Eastern Swamp Deer (Barasingha).
  - **Exceptional Birdlife:** The Agoratoli range hosts approximately **70% of Kaziranga's 350 recorded bird species**, making it a premier spot for migratory waterfowl and wetland raptors.
- **Verification Criteria:** Must mention the Big 5 (Rhino, Tiger, Elephant, Buffalo, Swamp Deer) and ~70% of the park's 350 bird species.

---

#### Question 17
- **Exact Copy-Paste Prompt:**
  ```text
  Are trained naturalists or guides provided with the safari at Machaan Wilderness Lodge?
  ```
- **Source Document:** `Karnataka\Nagarhole\Machaan Wilderness Lodge Property Update.png`
- **Section:** `PROS OF STAYING AT MACHAAN`, `SAFARI`
- **Expected Ground Truth Answer:**
  Yes. Machaan Wilderness Lodge features a dedicated in-house **team of 4 skilled naturalists with good English communication skills** who accompany guests on nature trails and safari activities.
- **Verification Criteria:** Must cite the team of 4 skilled naturalists with good English communication.

---

### Category 4: Activities & Experiences

#### Question 18
- **Exact Copy-Paste Prompt:**
  ```text
  What activities can guests do at Agoratoli Jungalow apart from safari?
  ```
- **Source Document:** `Assam\Kaziranga\AGORATOLI JUNGALOW Property Update (1).png`
- **Section:** `EXPERIENCES & ACTIVITIES`, `AMENITIES`
- **Expected Ground Truth Answer:**
  Apart from safaris, guests can enjoy:
  - Village walks and local e-auto rides through rural Assamese hamlets.
  - Authentic interaction with the local **Misingi tribal community**.
  - Cycling around the 5-acre estate, tea gardens, and nearby villages.
  - Guided walking excursion to a **perennial 60-ft waterfall** (2 km walk along the river).
  - On-site kitchen garden activities (strawberry picking, horticulture) and catch-and-release fish pond.
  - Indoor games (table tennis, board games).
  - Day visits to nearby tea factories, the local Orchid Park, vintage vehicles museum, and weavers' resource center.
- **Verification Criteria:** Must mention tribal interaction (Misingi), 60-ft waterfall walk, village walks/cycling, and kitchen garden / fish pond.

---

#### Question 19
- **Exact Copy-Paste Prompt:**
  ```text
  Does Kathoni offer cultural, village or community-based experiences?
  ```
- **Source Document:** `Assam\Kaziranga\Kathoni Property Update.png`
- **Section:** `OFFERINGS`, `OTHER EXPERIENCES AT THE PROPERTY`
- **Expected Ground Truth Answer:**
  Yes. Kathoni provides several rich community and cultural activities:
  - **Village Visits:** Walking strolls through the rural village to meet local residents and understand their way of life.
  - **Traditional Bihu Performances:** Live Bihu folk song and dance performed by community artists.
  - **Karbi Hill Tribe Interaction:** Guided village visit and forest hike with the Karbi tribal community.
  - **Tea Garden Tours:** Exploring the adjacent tea estate culture.
  - **Interactive Cooking Sessions:** Guests handpick fresh vegetables from the on-site organic farm and cook Assamese dishes over woodfire.
- **Verification Criteria:** Must cite village visits, traditional Bihu performance, Karbi tribal interaction, and woodfire farm cooking.

---

### Category 5: Food & Dietary Requirements

#### Question 20
- **Exact Copy-Paste Prompt:**
  ```text
  Are meals included in the standard room rate, and what meal plan options are available at Bagh Tola?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Section:** `PRICE RANGE`, `DINING EXPERIENCE`
- **Expected Ground Truth Answer:**
  Yes, meals are included. Bagh Tola rates start from approximately **₹24,000 onwards per night on an APAI (American Plan All Inclusive)** basis, which includes room accommodation and all major daily meals (breakfast, lunch, dinner, and dining experiences). Meals feature freshly prepared Indian cuisine with seasonal local produce, with bonfire and riverside setups available on request.
- **Verification Criteria:** Must specify the **APAI (American Plan All Inclusive)** meal plan and the indicative ₹24,000 price point.

---

### Category 6: Guest Profiles & Specializations

#### Question 21
- **Exact Copy-Paste Prompt:**
  ```text
  Would Bagh Tola work well for wildlife enthusiasts, photographers or serious birdwatchers?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Section:** `IDEAL FOR`, `WHY CHOOSE BAGH TOLA?`, `NEW ADDITIONS`
- **Expected Ground Truth Answer:**
  Yes, exceptionally well. Bagh Tola is explicitly designated as **"IDEAL FOR: Wildlife Enthusiasts, Birders and Photographers, and Nature Immersion Travellers."**
  Specific operational assets include:
  1. **Stationed Safari Infrastructure:** 2 in-house naturalists and **2 private modified gypsies stationed permanently at the lodge**, enabling flexible and customized game drives.
  2. **On-Property Wildlife Features:** A private 30-acre forest area with an **active watering hole and raised viewing machaan** for photography without leaving the lodge.
  3. **Strategic Location:** Situated near the Khitauli (5 km) and Magadhi gates with lower tourist congestion.
  4. **Founder's Camp:** 4 ultra-luxury tents offering dedicated spaces and privacy for photography teams and equipment.
- **Verification Criteria:** Must confirm suitability and highlight the private modified gypsies, on-site watering hole with machaan, and dedicated in-house naturalists.

---

### Category 7: Responsible Tourism & Conservation

#### Question 22
- **Exact Copy-Paste Prompt:**
  ```text
  What conservation initiatives does Red Panda Outpost support?
  ```
- **Source Document:** `Nepal\Red Panda Outpost Property Update.png`
- **Section:** `INTRODUCTION`, `WHY CHOOSE RED PANDA OUTPOST?`
- **Expected Ground Truth Answer:**
  Red Panda Outpost (Pugdundee Safaris) in Jaubari, eastern Nepal near the Singalila National Park border:
  - Operates as a **community-led conservation initiative** developed in direct partnership with local forest authorities and mountain communities.
  - Promotes **research-based, low-impact ecotourism** strictly limiting visitor volume to protect high-altitude wildlife habitats.
  - Trains and employs **local community members as specialized red panda trackers**, providing sustainable alternative livelihoods while contributing to scientific tracking and anti-poaching observation.
- **Verification Criteria:** Must highlight community-led conservation, trained local trackers, and low-impact ecotourism in Singalila.

---

#### Question 23
- **Exact Copy-Paste Prompt:**
  ```text
  Which properties in our database have the strongest conservation or community engagement programmes?
  ```
- **Source Document:** Corpus-wide (`Dolkhar Ladakh`, `Red Panda Outpost`, `Agoratoli Jungalow`, `Sariska Lodge`)
- **Section:** `WHY CHOOSE?`, `PROS`, `INTRODUCTION`
- **Expected Ground Truth Answer:**
  The standout properties with documented conservation and community engagement programs are:
  1. **Dolkhar Ladakh (Leh):** Operates under a strict **zero-waste and zero-plastic policy**; constructed with compressed stabilized earth blocks, poplar, and willow; built in collaboration with **40+ local Ladakhi artisans**.
  2. **Red Panda Outpost (Eastern Nepal):** Community-led research ecotourism supporting red panda habitat protection; trains and employs local community trackers.
  3. **Agoratoli Jungalow (Kaziranga):** Eco-certified property (TOFT 2024 Runner-up Best Homestay); active Mising tribal community engagement and local organic kitchen garden sourcing.
  4. **Sariska Lodge (Rajasthan):** Built across **15 acres of privately afforested/restored land** on the edge of Sariska Tiger Reserve, operating as a low-impact ecological sanctuary.
- **Verification Criteria:** Must cite at least 3 of these properties and their concrete initiatives (e.g. Dolkhar's zero-waste / 40+ artisans, Red Panda Outpost's local trackers).

---

### Category 8: Sales Pitches & Comparative Analysis

#### Question 24
- **Exact Copy-Paste Prompt:**
  ```text
  Give me the top five selling points of KAAV Safari Lodge that I can use when presenting it to an overseas travel partner.
  ```
- **Source Document:** `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
- **Section:** `WHY CHOOSE KAAV?`, `PROS OF STAYING AT KAAV`
- **Expected Ground Truth Answer:**
  1. **Guaranteed Safari Permit Allocation:** Assured safari seat allocation under the forest department quota (2 morning seats, 4 afternoon seats)—a major relief for international agents in high-demand Kabini.
  2. **Dual Land and River Wildlife Access:** Both classic Nagarhole forest jeep drives and Kabini River boat safaris / coracle rides.
  3. **Intimate Low-Inventory Luxury:** Only 7 forest-facing keys (including luxury tents and a 930 sq.ft private pool villa), preventing resort crowds.
  4. **Dedicated Expert Naturalists:** In-house guiding team leading specialized walks, kayaking, and birding (~300 species).
  5. **Seamless Circuit Routing:** Conveniently located just 72 km (1.5 hrs) from Mysore Airport, pairing naturally with Mysore, Coorg, and Wayanad itineraries.
- **Verification Criteria:** Must present 5 structured selling points including guaranteed safari quota, 7 keys, dual land/boat safaris, and naturalists.

---

#### Question 25
- **Exact Copy-Paste Prompt:**
  ```text
  Compare KAAV Safari Lodge and Bagh Tola for a luxury international client. Include location, accessibility, accommodation, safari, activities, facilities, food and overall experience.
  ```
- **Source Documents:**
  - `Karnataka\Kabini\Kaav Safari Lodge Property Update.png`
  - `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Expected Ground Truth Answer:**
  | Dimension | KAAV Safari Lodge | Bagh Tola |
  |---|---|---|
  | **Location & Park** | Kabini, Karnataka — southern fringe of Nagarhole National Park | Bandhavgarh buffer, Madhya Pradesh — near Khitauli & Magadhi gates |
  | **Accessibility** | Mysore Airport (72 km / 1.5 hrs); Bangalore Airport (~4.5 hrs) | Jabalpur Airport (203 km / 3.5 hrs); Khajuraho Airport (226 km / 5 hrs) |
  | **Inventory & Rooms** | 7 keys: 4 Superior Rooms (450 sq.ft), 2 Luxury Tents, 1 Pool Villa (930 sq.ft) | 10 units: 6 Cozy Safari Tents and 4 Elevated Luxury Tents (Founder's Camp) |
  | **Safari Experience** | Assured Forest Dept seat quota (2 AM / 4 PM); land jeeps + Kabini River boat safaris | Jeeps to Magadhi, Khitauli, Tala; 2 stationed modified gypsies; private night buffer drives |
  | **Activities** | Boat safaris, coracle rides, kayaking, birding (~300 spp), cycling | On-site watering hole birding, raised machaan, nature trails, guided stargazing |
  | **Facilities & Pool** | Outdoor swimming pool, alfresco dining lounge | Swimming pool, raised machaan over watering hole, bonfire decks |
  | **Food & Dining** | In-house alfresco dining, Indian & Continental set menu, custom timings | Fresh seasonal Indian cuisine, indoor/outdoor dining, bonfire/riverside setups (APAI) |
  | **Overall Experience** | Lush South Indian riverine canopy retreat with water-based wildlife | Intimate Central Indian tiger camp with private 30-acre forest and dedicated vehicles |
- **Verification Criteria:** Must compare both properties across the requested dimensions accurately.

---

#### Question 26
- **Exact Copy-Paste Prompt:**
  ```text
  What type of client would you NOT recommend Bagh Tola to, and why?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Section:** `TRAVEL INN RECOMMENDS`
- **Expected Ground Truth Answer:**
  The sales team should **NOT recommend the base category "Cozy Safari Tents"** to comfort-focused luxury clients or travellers expecting spacious bedrooms and large contemporary bathrooms, as their compact size may not meet high luxury expectations.
  Instead, Travel Inn specifically advises booking **only the newly launched Luxury Tents in the Founder's Camp** cluster for discerning clients, families, or photographers seeking elevated space and private dining.
- **Verification Criteria:** Must cite the negative recommendation against the base category Cozy Safari Tents due to compact room and bathroom size.

---

### Category 9: Portfolio-Wide "Quick Search" Questions

#### Question 27
- **Exact Copy-Paste Prompt:**
  ```text
  Which properties have fewer than 20 rooms?
  ```
- **Source Document:** Portfolio-wide structured facts / Accommodations
- **Expected Ground Truth Answer:**
  The properties in the portfolio with fewer than 20 rooms include:
  - **Kathoni** (Kaziranga): 2 rooms
  - **Agoratoli Jungalow** (Kaziranga): 3 rooms
  - **Haldu Tola** (Pench): 4 rooms
  - **Varenya Life** (Chikmagalur): 4 rooms
  - **The Postcard in the Himalayan Willows** (Leh): 5 rooms
  - **Camp TigerLily** (Dudhwa): 6 units
  - **Kinwani House** (Rishikesh): 6 rooms
  - **Dolkhar Ladakh** (Leh): 7 villas
  - **KAAV Safari Lodge** (Kabini): 7 units
  - **Red Panda Outpost** (Nepal): 7 rooms
  - **Outpost 12** (Kanha): 9 rooms
  - **Bagh Tola** (Bandhavgarh): 10 units
  - **Sitara Himalaya** (Manali): 10 rooms
  - **Sariska Lodge** (Sariska): 10 units
  - **Vayal Veedu** (Wayanad): 10 units
  - **Cabo Serai** (Goa): 11 cottages/tents
  - **Jaagir Manor** (Dudhwa): 13 units
  - **Guleria Kothi** (Varanasi): 15 rooms
  - **Rambha Palace** (Chilika): 16 rooms
  - **Saj in the Forest** (Pench): 17 rooms
  - **The Nanee** (Bhaktapur): 18 rooms
  - **Utsav Camp Sariska** (Sariska): 18 units
- **Verification Criteria:** Must list the key boutique/intimate properties under 20 rooms accurately from the database without hallucinating large hotel chains.

---

#### Question 28
- **Exact Copy-Paste Prompt:**
  ```text
  Which properties are closest to the airport?
  ```
- **Source Document:** Portfolio-wide Quick Facts (Distance from Airport)
- **Expected Ground Truth Answer:**
  The properties with the shortest distance and driving time to an airport are:
  1. **Dolkhar Ladakh (Leh):** Approx. **4.3 km / 15 minutes** from Leh Airport (Kushok Bakula Rimpochee Airport).
  2. **DoubleTree by Hilton Bengaluru Airport:** Under **12 km / ~15 minutes** from Kempegowda International Airport (BLR).
  3. **The Postcard in the Himalayan Willows (Leh):** Approx. **14 km / 25 minutes** from Leh Airport.
  4. **Courtyard by Marriott Siliguri:** Approx. **14 km / 31 minutes** from Bagdogra Airport (IXB).
- **Verification Criteria:** Must identify Dolkhar Ladakh (4.3 km / 15 mins) as the closest, along with Siliguri / Postcard Leh.

---

#### Question 29
- **Exact Copy-Paste Prompt:**
  ```text
  Which properties are closest to the safari gate?
  ```
- **Source Document:** Portfolio-wide Quick Facts (Nearest Gate)
- **Expected Ground Truth Answer:**
  The properties with the shortest transfer times to safari entry gates are:
  1. **Camp TigerLily (Dudhwa / Kishanpur):** Just **2 km / 5 minutes** from Kishanpur Gate.
  2. **Agoratoli Jungalow (Kaziranga):** Just **2 minutes** from the Agoratoli (Eastern) Gate.
  3. **Bagh Tola (Bandhavgarh):** Approx. **5 km / 15 minutes** from Khitauli Gate.
  4. **Machaan Wilderness Lodge (Nagarhole):** Approx. **5 km** from Nagarhole National Park entry.
  5. **Utsav Camp Sariska (Sariska):** Approx. **7 km** from Tehla Gate.
- **Verification Criteria:** Must identify Camp TigerLily (2 km / 5 mins) and Agoratoli Jungalow (2 mins) at the top of the list.

---

#### Question 30
- **Exact Copy-Paste Prompt:**
  ```text
  Which properties are good for families?
  ```
- **Source Document:** Portfolio-wide `IDEAL FOR` & `INVENTORY` sections
- **Expected Ground Truth Answer:**
  Properties specifically suited and tagged for families include:
  1. **Agoratoli Jungalow (Kaziranga):** Explicitly categorized under "IDEAL FOR: families"; features 2 triple-bedded family rooms, a kitchen garden (strawberry picking), catch-and-release fish pond, and indoor games.
  2. **Bagh Tola (Bandhavgarh):** Features the newly launched "Founder's Camp" cluster of 4 luxury tents with private common space, ideal for families travelling together.
  3. **Vythiri Resort (Wayanad):** Explicitly tagged "IDEAL FOR: Families, Nature and Wellness Travellers", offering spacious multi-bedroom family villas, pool villas, and gentle rainforest walks.
  4. **Courtyard House Kanha:** Features expansive lawn areas, interconnected family room options, and child-friendly wilderness orientation.
  5. **Machaan Wilderness Lodge (Nagarhole):** Features multi-bed Planter's Den and Tamarind cabins, an outdoor swimming pool, and evening wildlife documentary screenings.
- **Verification Criteria:** Must name Agoratoli Jungalow (triple rooms / games), Bagh Tola (Founder's Camp), and Vythiri Resort.

---

## Boundary Testing: Deliberate "I Don't Know" Verification

These two questions are deliberately included to confirm that your RAG assistant **gracefully declines to answer** when data is missing, rather than fabricating or hallucinating facts.

#### Question 31 (Boundary Test — Star Rating)
- **Exact Copy-Paste Prompt:**
  ```text
  What is Taj Mahal, New Delhi's official star rating?
  ```
- **Source Document:** `Delhi\Taj Mahal Delhi Property Update.png`
- **Expected RAG Behavior:**
  - **Correct Assistant Behavior:** The assistant should state clearly that the property documents do not specify an official government or numerical star rating (e.g. "5-star"). The documents describe it as an iconic luxury hotel managed by IHCL / Taj Hotels.
  - **Failing Behavior:** Confidently asserting "It is a 5-star hotel" (hallucination, as numerical star ratings are completely absent from the dataset).

---

#### Question 32 (Boundary Test — Foreign Currency Payment)
- **Exact Copy-Paste Prompt:**
  ```text
  Does Bagh Tola accept cash payment in foreign currencies such as USD or GBP?
  ```
- **Source Document:** `Madhya Pradesh\Bandhavgarh\Bagh Tola Property Update.png`
- **Expected RAG Behavior:**
  - **Correct Assistant Behavior:** The assistant should honestly state that the property sheets do not contain information regarding payment methods, foreign currency acceptance, or currency exchange.
  - **Failing Behavior:** Claiming that Bagh Tola accepts or does not accept USD/GBP without source evidence.

---

## How to Test & Review With Us
1. Open your chatbot UI at `http://127.0.0.1:5173/`.
2. Copy each question prompt above verbatim.
3. Paste into the chat box and submit.
4. Copy the assistant's answer and paste it back into this chat.
5. We will evaluate the assistant's response against the expected ground truth and verify:
   - Factual accuracy of numbers (distances, hours, room counts, prices).
   - Correct entity identification and citations.
   - Grounding and absence of hallucinations.
