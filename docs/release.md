Dansk kortværksted med interaktiv ramme, 1954-prøvebillede, vedvarende jobkø,
GeoTIFF og A0/A1/A2/A3-PDF. Browseren kan lukkes under arbejdet.

Installér via TrueNAS **Custom App / Install via YAML**. Vælg selv et separat
dataset, en ledig port og en privat adgangskode på mindst 16 tegn.

- `truenas.yaml`: installation fra versionsmærket GHCR-image.
- `aarhus-plotter-1.0.3-linux-amd64.tar.gz`: færdigbygget Linux/AMD64-image,
  som også kan hentes fra denne release uden registry-login.
- `truenas-offline.yaml`: brug efter `docker load` af imagearkivet.
- `SHA256SUMS`: kontrolsummer for de tre installationsfiler.

Den offentlige imagefil er et alternativ, hvis GHCR-synlighed eller adgang
forhindrer direkte imagehentning. Kontroller den aktuelle teststatus i
[docs/validation.md](https://github.com/Anders-kramer/aarhus-plotter/blob/main/docs/validation.md).

1954 er efterkrigsmateriale. Billeddata og kildeadgangsparametre medfølger ikke.
Respektér Hexagons og Miljøportalens vilkår for personlig kopiering og privat print.
Fuld byeksport og fysisk strømsvigt er ikke testet.
