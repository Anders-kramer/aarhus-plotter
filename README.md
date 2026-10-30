# Aarhus Plotter

Et dansk kortværksted til personlig eksport af Aarhus-ortofoto fra **1954** til
georefereret GeoTIFF og PDF i A0, A1, A2 eller A3.
1954 er efterkrigsmateriale, ikke et autentisk foto fra 1940–1945.

## Brug

1. Åbn appen direkte på dit lokale netværk.
2. Vælg en områdeprofil, tegn en ramme, eller flyt og ændr rammen.
3. Hent et lille 1954-prøvebillede og kontrollér motivet.
4. Vælg papir, retning, margen, PDF-DPI og kildepixel.
5. Start eksporten. Hent GeoTIFF, PDF og forhåndsvisning fra joboversigten.

Den moderne OpenStreetMap-baggrund er kun til orientering og eksporteres aldrig.
Profilerne er omtrentlige rektangler, ikke administrative grænser. Avanceret
BBOX er i EPSG:25832. Kortets ramme viser en geografisk tilnærmelse af den
projekterede udskæring; GeoTIFF bruger de præcise viste UTM-koordinater.

Browseren ejer ikke jobbet. En enkelt baggrundsarbejder henter og behandler
jobs på serveren. Jobdatabase, færdige billedfelter, hændelser og resultater
ligger i `/data`. Ved genstart markeres aktive jobs som afbrudte, og du kan
genoptage dem. Jobs, som endnu var i kø, starter normalt.

Import understøtter de kendte v4-indstillinger. En gammel jobfil med
adgangsparametre eller en anden WMS-adresse afvises. Fjern disse felter; appen
finder selv den officielle kilde. Import gennemfører aldrig eksterne
forespørgsler til en adresse fra filen.

## Installation med Docker Compose

Kræver Docker med Compose. Bash:

```bash
git clone https://github.com/Anders-kramer/aarhus-plotter.git
cd aarhus-plotter
umask 077
docker compose up -d --build
```

Åbn <http://127.0.0.1:8088>. Compose-eksemplet binder kun til localhost.
Image kører som UID/GID `10001:10001`, med read-only root og uden capabilities.
Ingen Docker-socket eller privileged mode.

Et færdigbygget Linux/AMD64-image findes også som offentligt releasearkiv.
Det kan installeres uden registry-login:

```bash
VERSION=1.4.0
RELEASE_URL="https://github.com/Anders-kramer/aarhus-plotter/releases/download/v$VERSION"
curl -fLO "$RELEASE_URL/aarhus-plotter-$VERSION-linux-amd64.tar.gz"
curl -fLO "$RELEASE_URL/truenas.yaml"
curl -fLO "$RELEASE_URL/truenas-offline.yaml"
curl -fLO "$RELEASE_URL/SHA256SUMS"
sha256sum -c SHA256SUMS
gzip -dc "aarhus-plotter-$VERSION-linux-amd64.tar.gz" | sudo docker load
```

Brug derefter `truenas-offline.yaml` med dine verificerede lokale værdier.
Den bruger kun det allerede indlæste image (`pull_policy: never`).

## TrueNAS Custom App / Install via YAML

Brug [`deploy/truenas.yaml`](deploy/truenas.yaml), ikke et vilkårligt
GitHub-repository som appkatalog. Filen bruger et versionsmærket GHCR-image.
Se [TrueNAS' installationsvejledning](https://apps.truenas.com/managing-apps/installing-custom-apps/).

1. Kontrollér din ledige LAN-port, pool og dataset i TrueNAS.
2. Opret et separat dataset til appen, og giv UID/GID 10001 adgang til
   undermappen `data`. Del ikke dine mediebiblioteker med containeren.
3. Erstat eksempel-IP `192.0.2.10`, `POOL` og stier i YAML med dine verificerede
   værdier. Eksempel-IP'en er en dokumentationsadresse og kan ikke bruges direkte.
4. I Apps → Discover Apps → menu → Install via YAML: indsæt filen og installér
   med navnet `aarhus-plotter`.

Eksempel på klargøring via Bash, **efter** dataset og placering er valgt:

```bash
APP_ROOT=/mnt/POOL/aarhus-plotter
sudo install -d -o 10001 -g 10001 -m 700 "$APP_ROOT/data"
umask 077
```

Appen kræver ikke login. Alle enheder med netværksadgang til appen kan bruge den og hente eller slette eksportjob. Installationen er beregnet til dit lokale netværk.

### Drift, opdatering og sikkerhedskopi

- Start/stop i TrueNAS Apps. Med Compose: `docker compose stop` / `docker compose up -d`.
- Tag snapshot/backup af hele datadatasættet, helst mens appen er stoppet.
  SQLite-database, eventuelle WAL-filer og billedfelter hører sammen.
- Opdatér ved at ændre image-tag til en ny verificeret version og geninstallere.
  Stop appen og tag snapshot først. Brug aldrig to instanser på samme volume.
- Rollback: stop, gendan datavolume fra snapshot hvis databaseskemaet er ændret,
  og gendan det tidligere image-tag.
- Sletning af et job fjerner dets billedfelter, resultater og databaseposter.
  UI kræver bekræftelse; aktive jobs skal først annulleres.

## Robusthed og begrænsninger

Hvert billedfelt gemmes som en PNG via flush/fsync og atomisk rename. Først
derefter registreres fremdrift. TIFF samles på ny fra disse felter, så en
buffer i en afbrudt TIFF aldrig bruges som bevis for en færdig tile.
PDF og TIFF offentliggøres først efter afsluttet filskrivning. Download er
kun tilgængelig for færdige jobs og sendes som filstream.

Ét eksportjob kører ad gangen, med én WMS-forespørgsel ad gangen. Et historisk kortbillede eller manuelt
prøvebillede kan hente samtidigt, så maksimum er to. Netværksfejl forsøges
højst tre gange; 429 og serverfejl bruger ventetid. En igangværende
netværksforespørgsel kan forsinke annullering op til dens timeout.
Diskkontrol foretages før og løbende under eksport. Der er ingen fast pixelgrænse
pr. job; køen har højst 10 ventende jobs. Områdevalget gælder fortsat Aarhus-regionen.
Før start vises konservativ diskreserve, faktisk fri plads og et groft tidsinterval.
Intervallet bygger på 1–8 sekunder pr. felt og 2–20 millioner pixels/sekund til
samling, ikke på en målt NAS-kapacitet. Køtid og kildeforsinkelser kommer oveni.

Rasteret behandles i vinduer; det komplette bykort indlæses ikke i RAM.
PDF-billedfelter komprimeres tabsfrit og skrives løbende til disk. Hele PDF-billedet
beholdes ikke i RAM. PDF-krydsreferencer bruger 64-bit filpositioner.
2 GB containerhukommelse er sat som en driftsgrænse, ikke et løfte om at enhver
stor eksport vil lykkes. Diskestimatet er en konservativ reserve, ikke en
præcis filstørrelse. Hele byeksporter er ikke verificeret ved udgivelsen.

PDF-opløsning er som standard **Fuld kildeopløsning**: alle hentede pixels
bevares uden nedskalering eller ekstra JPEG-komprimering. Menuen tilbyder også
50-DPI-trin under kildens maksimale opløsning på det valgte papir (fx fuld
779,5 DPI, 750, 700 … 50). En mindre kilde opskaleres aldrig til nye pixels.
Appen viser både kildens maksimum og PDF-filens faktiske pixels/DPI.
Kilden leverer selv JPEG; tabsfri PDF kan ikke genskabe detaljer tabt hos kilden.
Print i faktisk størrelse / 100 %. Gamle jobs med 240 DPI kan fortsat genoptages.

## Kilde og billedrettigheder

1954-kilden findes dynamisk fra
[Miljøportalens officielle metadata](https://datakatalog.miljoeportal.dk/api/datasets/urn%3Admp%3Ads%3Aortofoto-1954?include=wmsSource).
Kun den kendte HTTPS-vært, WMS-sti og lag accepteres. Adgangsparametre
holdes i serverens hukommelse og gemmes ikke i jobs, logs eller eksportmetadata.
De indgår ikke i identiteten af de gemte billedfelter.

DDO® 1954 tilhører Hexagon. Ifølge de officielle vilkår må privatpersoner selv
foretage digitale kopier til sig selv/husstanden og papirprint til privat
brug i den nære kreds. Anden brug kræver afklaring med rettighedshaver,
herunder ekstern printbutik. Ingen fri genudgivelse eller ubegrænset massehentning
er lovet. Softwarelicensen gælder **ikke** billeddata.

Kilder kontrolleret 19.–20. oktober 2026:

- [Særlige vilkår](https://miljoeportal.dk/dataansvar/saerlige-vilkaar-for-brug-i-datakataloget/)
- [Rettigheder til baggrundskort og ortofotos](https://support.miljoeportal.dk/hc/da/articles/13877948639005-Danmarks-Arealinformation-Rettighederne-til-brug-af-baggrundskort-og-ortofotos)
- [OSM tile-policy](https://operations.osmfoundation.org/policies/tiles/): kun interaktiv
  orientering, synlig kreditering, normal browsercache, ingen prefetch/offlineeksport.

Ingen luftfotos, private jobs eller kildeadgangsparametre distribueres i repository
eller container. Testbilleder er syntetiske.

## Udvikling og tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8088 --workers 1
```

GitHub Actions tester Python, JavaScript-syntaks og et begrænset Docker-image.
Tags `v*` udgiver versionsmærkede GHCR-images efter tests.
Pakkens synlighed skal være offentlig; repositoryets synlighed alene er ikke nok.
Se [teststatus](docs/validation.md) for præcist gennemførte kontroller.

Eksportgeometri og tileberegning viderefører ideerne fra brugerens tidligere
Aarhus 1954 Windows-eksportør. Jobpersistens, atomisk spool, adgangsbeskyttelse,
netværksgrænser og webapp er skrevet til serverudgaven.

## Historisk kortbaggrund

1954-luftfoto er standardbaggrund. Vælg Moderne orienteringskort i Kortbaggrund
for at sammenligne. Rammen kan tegnes, flyttes og ændres på begge baggrunde.
Efter zoom/panorering hentes ét billede af den synlige flade (højst 1024 pixels pr. side),
ikke et offlinekort eller en forudhentning. Kortet bruger WMS EPSG:3857 for korrekt
placering i Leaflet; eksporten bruger fortsat EPSG:25832 og den valgte kildepixel.
Oversigtsbilledet er ikke eksportens opløsning. Kildens adgangsparametre forbliver på serveren.

## Flere historiske kortkilder (1.4.0)

Kortkilden vælges i brugerfladen, før område, prøvebillede og eksport.
Kilde-id gemmes sammen med hvert nyt job; gamle jobs uden kilde-id fortsætter
som **DDO 1954**. Kun godkendte, kendte korttjenester accepteres – WMS-URL og
adgangsnøgler kan ikke angives i JSON-import, API eller browser.

| Kilde-id | Materiale | Tilgængelighed | Anbefalet eksportafstand |
| --- | --- | --- | --- |
| `dmp_1954` | DDO 1954, Hexagon | Standard, fungerende offentlig katalogrelation | 0,25 m/pixel |
| `lave_maalebordsblade` | Lave målebordsblade, Datafordeleren | API-nøgle og bestået automatisk billedtest | 1 m/pixel som **praktisk forslag**, ikke dokumenteret originalopløsning |
| `lw_1944` | Luftwaffe 1944, FlyFotos.dk | Låst til verificeret adgang, rettigheder og WMS | Ikke fastlagt |
| `ia_1945` | Allierede 1945, FlyFotos.dk | Låst til verificeret adgang, rettigheder og WMS | Ikke fastlagt |

### Aktivering af Datafordeler-kort

Datafordelerens dokumenterede WMS-tjeneste:
https://datafordeler.dk/dataoversigt/historiske-kort-og-data/lave-maalebordsblade-wms/

1. Opret en API-nøgle hos Datafordeleren i henhold til deres vilkår.
2. Angiv den **udelukkende som servermiljøvariabel** `PLOTTER_DATAFORDELER_APIKEY`
   i TrueNAS-appens konfiguration / Docker Compose. Send ikke nøglen til
   Plotters API eller indsæt den i eksportindstillinger.
3. Genstart appen. Før aktivering kontrollerer serveren GetCapabilities, lag,
   JPEG og EPSG:25832/EPSG:3857 samt et faktisk billede i begge koordinatsystemer.
   Ved fejl forbliver kilden låst; kontrollér nøgle/adgang og genstart for nyt forsøg.
4. Hent et lille prøvebillede før et stort eksportjob. Den automatiske test
   kontrollerer adgang ved Aarhus, ikke dækning eller historisk årstal for hele udsnittet.

Korttjenesten viser kortblade fra **1901–1971**, og det enkelte blads revision
behøver ikke være 1940–1945. Plotter udleder derfor ikke et specifikt årstal
for disse eksporter. Kontrollér årstal og om ønsket udsnit er dækket i kilden.

FlyFotos.dk tilbyder særskilt WMS-adgang. LW1944 har også en offentlig
viser med fungerende WMS, men stor eksport fra denne er ikke rettighedsafklaret.
Begge er registreret som inaktive kilder indtil URL-format, lag, aftale og
eksportrettigheder er bekræftet:
https://flyfotos.dk/da-dk/Produkter/Adgang

**Rettigheder:** Download og mulighed for print indebærer ikke automatisk
tilladelse til offentliggørelse, massehentning eller deling på en spilserver.

Se [verifikationsrapporten](docs/historical-sources.md) for konkrete kilder, adgangsblokeringer og teststatus.

Gemte billedfelter bindes atomisk til kilde-id, BBOX, pixelafstand og koordinatsystem.
Genoptagelse med en anden kilde/geometri afvises uden at overskrive felterne.
Gamle jobs uden kilde-id eller manifest behandles som DDO 1954; ingen databaseændring kræves.
