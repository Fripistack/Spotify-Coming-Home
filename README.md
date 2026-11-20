# Muziek Thuiskomst

Home Assistant-integratie die je Spotify-muziek laat meekomen naar binnen. Luister je in de auto naar Spotify en kom je thuis, dan gaat dezelfde muziek op dezelfde plek verder op je Sonos-speakers.

**Versie: 1.0.0**

## Wat doet het?

Per persoon (bijvoorbeeld jij en je partner, elk met een eigen Spotify-account):

1. Je person-entiteit springt naar **Thuis**.
2. De integratie controleert:
   - ligt het binnen het tijdvenster (standaard 07:00–23:00, ook over middernacht mogelijk);
   - is verder niemand thuis (aan/uit te zetten);
   - speelt Spotify, of is het in de laatste *x* minuten gepauzeerd (de telefoon pauzeert vaak als de auto-Bluetooth wegvalt).
3. Optioneel: met de Bluetooth-sensor van de Companion app (Android) wacht hij tot de auto uit is, zodat de muziek in de auto doorloopt tot je uitstapt.
4. Daarna worden de speakers gegroepeerd, het volume gezet en wordt het afspelen via **Spotify Connect** naar de Sonos overgezet. Zelfde nummer, zelfde positie, de telefoon stopt.
5. Ziet Spotify de Sonos niet als Connect-apparaat, dan speelt de Sonos (noodroute) het huidige nummer zelf af en spoelt door naar de juiste plek.

Ga je weer weg terwijl hij op de auto wacht, dan breekt hij af.

## Vereisten

- De officiële **Spotify**-integratie in Home Assistant, per account één (Spotify Premium).
- De **Sonos**-integratie, en Spotify gekoppeld in de Sonos-app (voor elk account dat je gebruikt).
- Optioneel: Home Assistant **Companion app** op Android met de sensor *Bluetooth connection* aan.

## Installatie

1. HACS → ⋮ → *Aangepaste repositories* → `https://github.com/Fripistack/Spotify-Coming-Home`, type *Integratie*.
2. Installeer **Muziek Thuiskomst** en herstart Home Assistant.
3. Instellingen → Apparaten & diensten → *Integratie toevoegen* → **Muziek Thuiskomst**.
4. Doorloop de drie stappen: persoon + Spotify-account, speakers, logica.
5. Voor een tweede persoon voeg je de integratie gewoon nog een keer toe.

Later aanpassen: bij de integratie op **Configureren** klikken. Je kiest dan *Speakers en volume*, *Logica* of *Spotify-account*.

## Instellingen

| Instelling | Uitleg |
|---|---|
| Persoon | De person-entiteit die thuiskomt |
| Spotify-account | `media_player.spotify_...` van die persoon |
| Speakers | Eén of meer mediaspelers; de eerste is het groepshoofd |
| Spotify Connect-apparaat | Naam zoals Spotify het groepshoofd toont (leeg = naam eerste speaker) |
| Volume | Volume bij overzetten (uit te zetten) |
| Noodroute | Sonos speelt het nummer zelf af als Spotify Connect de speaker niet ziet |
| Alleen als verder niemand thuis is | Zet je dit uit, dan gebeurt het ook als er al iemand thuis is |
| Vanaf / Tot | Tijdvenster |
| Ook als net gepauzeerd | Aantal minuten dat een pauze nog meetelt |
| Bluetooth-sensor + naam auto | Wacht tot de auto-Bluetooth weg is |
| Maximaal wachten | Hoe lang hij maximaal op de auto wacht |

## Entiteiten (per persoon)

- `switch.muziek_thuiskomst_<naam>_automatisch_overzetten`: hele functie aan/uit (blijft bewaard na herstart).
- `button.muziek_thuiskomst_<naam>_nu_naar_speakers`: meteen overzetten, zonder voorwaarden.
- `sensor.muziek_thuiskomst_<naam>_status`: Klaar / Wacht tot auto uit is / Overgezet / Overgeslagen / Fout, met attribuut `reden`.
- `sensor.muziek_thuiskomst_<naam>_laatst_overgezet`: tijdstip.

Bij elke overzetting komt het event `muziek_thuiskomst_overgezet` voorbij, handig voor eigen automatiseringen.

## Problemen oplossen

- **Status "Fout: staat niet in de Spotify-apparatenlijst"**: open in HA de Spotify-mediaspeler en kijk bij *Bron* welke namen er staan. Kies die naam bij *Spotify Connect-apparaat*, of zet de noodroute aan.
- **Status "Overgeslagen"**: het attribuut `reden` zegt waarom (buiten tijdvenster, iemand thuis, Spotify speelde niet, ...).
- Spotify in HA ververst ongeveer elke 30 seconden; de integratie vraagt bij thuiskomst zelf een verversing aan.

## Versiegeschiedenis

### 1.0.0
2026-11-20. Eerste versie: meerdere personen, speakers kiezen en groeperen, tijdvenster, "alleen als niemand thuis", wachten tot de auto-Bluetooth weg is, Sonos-noodroute, schakelaar, status-sensoren en knop.
