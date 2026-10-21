# Ændringer

## 1.0.1

- Luk databaseforbindelser eksplicit efter hver transaktion.
- Kontrollér anonym hentning og eksport fra det udgivne GHCR-image på en ny Linux-runner.

## 1.0.0

- Dansk kortværksted med navngivne områder, tegnbar/redigerbar ramme og separat prøvebillede.
- SQLite-jobkø, atomisk billedspool, genoptagelse, annullering og bekræftet sletning.
- GeoTIFF og A0/A1/A2/A3 PDF med kildeangivelse og ærlig opløsningsberegning.
- Adgangsbeskyttelse, begrænset import og fast serverstyret billedkilde.
- Docker, Compose, TrueNAS YAML og GitHub Actions.

## 1.0.2

- Opdater aktuelle mål og koordinater selv når en redigeret ramme er for stor.
- Fjern forældede estimater, vis faktisk pixelantal og vejledning.
- Blokér eksport ved ugyldige indstillinger og ignorér forsinkede estimatsvar.
- Undgå dobbelt behandling når en ramme gemmes.

## 1.0.3

- Browserfiler genvalideres ved genindlæsning; versionsmærket JavaScript undgår gamle cachefiler.

## 1.1.0

- Fjernet fast pixelgrænse; beholdt kontrol af faktisk ledig diskplads.
- Viser fri plads, diskreserve og groft tidsinterval med forudsætninger.
- Historisk 1954-kort som valgfri baggrund (standard), med korrekt Web Mercator-projektion.
- Store TIFF-filer skrives eksplicit som BigTIFF.

## 1.2.0

- Fuld kildeopløsning som standard og dynamiske DPI-trin på 50 nedad.
- Tabsfri PDF, skrevet feltvis til disk med 64-bit krydsreferencer.
- Vis både kilde- og PDF-opløsning; disk- og tidsskøn tager PDF-størrelsen med.
- Verificeret pixelidentitet mellem GeoTIFF og PDF ved fuld opløsning.
