# Historical source verification — 30 October 2026

## DDO 1954

Default source. Live metadata resolution and RGB image retrieval verified on TrueNAS
with 1.3.1. The 60000 × 76000 pixel, 4425-tile production job completed before this update.
Legacy configurations without `source_profile` remain DDO 1954; no schema migration.

## Lave målebordsblade

The [official service documentation](https://datafordeler.dk/dataoversigt/historiske-kort-og-data/lave-maalebordsblade-wms/)
confirms the fixed endpoint `/LaveMaalebordsblade/topo20_lave_maalebordsblade/1.0.0/wms`
on `wms.datafordeler.dk`, layer `dtk_lave_maalebordsblade`, WMS 1.3.0,
EPSG:25832, JPEG/PNG and API-key or OAuth access. The implementation uses a
server-side API key and JPEG. EPSG:3857 for the interactive map is additionally
required and checked against capabilities and an actual image at startup.

Unauthenticated GetCapabilities returned HTTP 401. The user has no key yet.
Authenticated capabilities and actual Datafordeler imagery are **not verified**.
A key alone does not enable this source: startup checks layer/format/version,
inherited CRS declarations and nonuniform 128 × 128 RGB images in both CRSs.
Failure leaves this source disabled and does not print upstream errors or keys.
Restart after installing/correcting the key. The small image tests do not establish
full coverage or the edition date of individual sheets.

[KDS terms](https://datafordeler.dk/vejledning/brugervilkaar/kds-geografiske-data/)
include historical maps under CC BY 4.0. Exports credit KDS and identify resampling;
GeoTIFF includes the license URL. The series spans 1901–1971, not a single 1940 date.
1 m/pixel is a practical export default, not a verified native resolution.

## LW1944

The [public viewer](https://lw1944.flyfotoarkivet.dk/Default.aspx) and
[regional viewer](https://geomidt.flyfotoarkivet.dk/) expose a real public WMS:
`https://lw1944.flyfotoarkivet.dk/kort/service1.ashx?servicename=lw1944utm32`.
GetCapabilities returned WMS 1.1.1, layer `LW1944`, EPSG:25832.
A 789 × 1000 PNG GetMap for BBOX `565500,6211350,580500,6230350` succeeded.
Visual inspection confirms central Aarhus and much of the surrounding land;
the overview contains sheet joins, grid lines and a substantial blank area east
of the city over the bay. Full seamless coverage must not be claimed.
Three public zoom-16 tiles at centrum, harbour and Viby were also inspected;
these public samples are visibly soft. They do not establish original scan resolution.

The [provider's historical notes](https://lw1944.flyfotoarkivet.dk/Stories.aspx)
describe assembled photomaps and uncertain precise capture dates.
The [about page](https://lw1944.flyfotoarkivet.dk/About.aspx) credits the Royal
Danish Library and JO Informatik; purchase enquiries go to the library.
Capabilities say no access constraint, but this is not a documented grant for
bulk export or redistribution. No export agreement is available. Source remains
locked; no production downloader for this service is enabled.

## IA_1945

[FlyFotos.dk's coverage description](https://flyfotos.dk/da-dk/Eksempler/D%C3%A6kningskort)
lists near-national coverage, but this is not proof of complete coverage of the
specified Aarhus BBOX. Its public coverage query returned later local series;
absence of IA_1945 in that query is inconclusive (LW1944 was also absent).
No authenticated WMS, actual IA_1945 image or resolution has been verified.
The [WMS product](https://flyfotos.dk/da-dk/Produkter/Mere-om-WMS-l%C3%B8sningen)
requires supplied access credentials. User has no agreement. Source remains locked.

## Validation and rollout

Automated checks cover source selection, credential masking, WMS parameter
construction, failed capabilities/images, legacy jobs, persisted source IDs,
cross-source/geometry resume rejection, GeoTIFF/PDF output and stale UI responses.
Mocked optional-provider tests are explicitly not live provider verification.

Before production replacement: run the versioned image with an independent
temporary data volume, verify DDO live output and legacy SQLite compatibility,
confirm no active production jobs, save config and take a stopped ZFS snapshot.
Preserve the data mount and port. Do not downgrade and resume new non-DDO jobs
with 1.3.1: that old version cannot understand their source IDs.
