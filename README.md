# Aarhus Plotter

Et dansk kortværksted til personlig eksport af Aarhus-ortofoto fra **1954** til
georefereret GeoTIFF og PDF i A0, A1, A2 eller A3.
1954 er efterkrigsmateriale, ikke et autentisk foto fra 1940–1945.

## Brug

1. Log ind med din egen installationsadgangskode.
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
printf 'APP_PASSWORD=%s\n' "$(openssl rand -hex 24)" > .env
# Gem adgangskoden fra .env i din adgangskodeadministrator.
docker compose up -d --build
```

Åbn <http://127.0.0.1:8088>. Compose-eksemplet binder kun til localhost.
Image kører som UID/GID `10001:10001`, med read-only root og uden capabilities.
Ingen Docker-socket eller privileged mode.

Et færdigbygget Linux/AMD64-image findes også som offentligt releasearkiv.
Det kan installeres uden registry-login:

```bash
VERSION=1.1.0
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
3. Opret en adgangskodefil uden for `data` og hold den privat.
4. Erstat eksempel-IP `192.0.2.10`, `POOL` og stier i YAML med dine verificerede
   værdier. Eksempel-IP'en er en dokumentationsadresse og kan ikke bruges direkte.
5. I Apps → Discover Apps → menu → Install via YAML: indsæt filen og installér
   med navnet `aarhus-plotter`.

Eksempel på klargøring via Bash, **efter** dataset og placering er valgt:

```bash
APP_ROOT=/mnt/POOL/aarhus-plotter
sudo install -d -o 10001 -g 10001 -m 700 "$APP_ROOT/data"
umask 077
openssl rand -hex 24 | sudo tee "$APP_ROOT/password.txt" >/dev/null
sudo chown 10001:10001 "$APP_ROOT/password.txt"
sudo chmod 400 "$APP_ROOT/password.txt"
```

Der er ingen standardadgangskode. Minimum er 16 tegn. Brug kun et betroet
privat netværk; HTTP krypterer ikke forbindelsen. Ved adgang over andre netværk
skal en korrekt konfigureret HTTPS-proxy bruges. Ingen automatisk portåbning.

### Drift, opdatering og sikkerhedskopi

- Start/stop i TrueNAS Apps. Med Compose: `docker compose stop` / `docker compose up -d`.
- Tag snapshot/backup af hele datadatasættet, helst mens appen er stoppet.
  SQLite-database, eventuelle WAL-filer og billedfelter hører sammen.
- Gem adgangskodefilen separat og sikkert. Backup indeholder personlige billedkopier.
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
PDF-biblioteket beholder komprimerede billedobjekter frem til færdigskrivning.
2 GB containerhukommelse er sat som en driftsgrænse, ikke et løfte om at enhver
stor eksport vil lykkes. Diskestimatet er en konservativ reserve, ikke en
præcis filstørrelse. Hele byeksporter er ikke verificeret ved udgivelsen.

PDF-DPI er en øvre grænse for printbilledets opløsning. Et lille kildebillede
bliver ikke kunstigt opskaleret til nye pixels. UI viser den effektive
oprindelige opløsning på papiret. Print i faktisk størrelse / 100 %.

## Kilde og billedrettigheder

1954-kilden findes dynamisk fra
[Miljøportalens officielle metadata](https://arealdata-api.miljoeportal.dk/datasets/urn:dmp:ds:ortofoto-1954).
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
export APP_PASSWORD="$(openssl rand -hex 24)"
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
