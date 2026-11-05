# Source data and how to obtain them

The analysis uses only published aggregate statistics from GENESIS-Online, the database of the Federal Statistical Office of Germany (Statistisches Bundesamt, Destatis): https://www-genesis.destatis.de. None of the source files are included in this repository. This file lists each table, the files the scripts expect and how to obtain them.

## Access

Table downloads through the GENESIS web service require a free personal account. After registering at GENESIS-Online, create an API token in the account settings and store it locally:

```
cp .env.example .env
# edit .env: DESTATIS_GENESIS_TOKEN=<your token>
```

`make data` then downloads all tables with the parameters used for the published analysis (`scripts/acquire_genesis.py`). The token is sent only in request headers and is not written to any file other than your local `.env`, which is excluded from version control. Each download is stored unchanged under `data/raw/` together with a manifest that records the request parameters, retrieval time and SHA-256 checksum. The manifests of the files used for the published analysis (retrieved on 5 November 2026) are in `metadata/retrieval_manifests/`, and their checksums in `data/SHA256SUMS`:

```
sha256sum -c data/SHA256SUMS
```

## Tables

| Table | Content | Selection | Folder |
|---|---|---|---|
| 23131-0002 | Hospital discharges by principal diagnosis (ICD-10, three-digit), sex and age group; Germany | 2005–2024; ICD-10 C70, C71, C72, D32, D33, G91, I60, I61, I62, S06; without row compression | `genesis/23131-0002/` |
| 12411-0006 | Population on 31 December by sex and single year of age; Germany | 2005–2024; men and women | `genesis/12411-0006/` |
| 12421-0002 | 16th coordinated population projection by variant, sex and single year of age; Germany | 2030–2040; variants G2-L2-W1, W2, W3; men and women | `genesis/12421-0002/` |
| 23141-0102 | Operations and procedures in full inpatient care by OPS code (four-digit), sex and age group; Germany | 2019–2024; OPS 5-013, 5-015, 5-022, 5-023; without row compression | `genesis/23141-0102/` |
| 23131-0011 | Hospital discharges by federal state of treatment, principal diagnosis, sex and age group | 2022–2024; same ICD-10 codes; without row compression | `genesis/23131-0011/` |
| 12411-0013 | Population on 31 December by federal state, sex and single year of age | 2022–2024 | `genesis/12411-0013/` |
| 12421-0004 | 16th coordinated population projection by federal state, variant, sex and single year of age | 2030, 2035 and 2040 (one request each); variants G2-L2-W1, W2, W3 | `genesis/12421-0004/` |
| 23131-0012 | Hospital discharges by federal state of treatment and federal state of residence | 2024 | `genesis/23131-0012/` |
| 12421-0002 | As above, all 27 variants and 3 model calculations | 2030, 2034, 2035 and 2040 (one request each); men and women | `genesis_sensitivity/12421-0002/` |
| 12411-0041 | Annual average population by sex and single year of age; Germany | 2024 | `genesis_sensitivity/12411-0041/` |

Exact request parameters are given in the `data` target of the `Makefile` and in each manifest. The regional projection table exceeds the size limit for direct retrieval and is therefore requested one year at a time.

## Manual download

If the web service is not available, each table can be opened on GENESIS-Online by its code, restricted to the selection above and exported as "flat-file CSV" (ffcsv). Save the exported archive in the folder given above with a file name that ends in the year range used by the scripts (for example `..._2005-2024_uncompressed.zip` for 23131-0002, or `..._2030-2040.zip` for 12421-0002) and run `make all`.

## Terms of use

The data are published by the Federal Statistical Office of Germany. Please cite the source as "Statistisches Bundesamt (Destatis), GENESIS-Online", with the table code and retrieval date, and observe the terms of use published on GENESIS-Online.
