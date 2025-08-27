# MS MARCO-like content on Azure Search (Blob → Indexer → FastAPI)

This sample:
- Reads **existing content in Azure Blob Storage** under `doc_urls/` (PDF/Office) and `wiki_urls/` (HTML)
- Creates one **index** and two **blob data sources + indexers** (one per folder prefix)
- Exposes a **FastAPI** `/search` endpoint for your web client

> The indexer is configured for **content + metadata extraction** from PDFs/Office/HTML.
> No client-side keys are exposed; your web UI calls FastAPI, which uses the Search **query key**.

---

## Make sure python311 is installed as PyTerrier does not work with more recent versions currently

# if you're mounting azure to a local drive
.\rclone.exe config create wc azureblob sas_url="<SAS_URL>"
.\rclone.exe mount wc: Z: --vfs-cache-mode writes


# get the java path
PS C:\Users\milads> Get-Command java | Select-Object Source

Source
------
C:\Users\milads\AppData\Local\Programs\Eclipse Adoptium\jdk-21.0.8.9-hotspot\bin\java.exe


#set java path
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> # point JAVA_HOME at your JDK
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> $jdk = "C:\Users\milads\AppData\Local\Programs\Eclipse Adoptium\jdk-21.0.8.9-hotspot"
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> $env:JAVA_HOME = $jdk
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> 
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> # prepend JDK bin to this session's PATH
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> $env:Path = "$jdk\bin;$env:Path"
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> 
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> # verify
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> java -version
openjdk version "21.0.8" 2025-07-15 LTS
OpenJDK Runtime Environment Temurin-21.0.8+9 (build 21.0.8+9-LTS)
OpenJDK 64-Bit Server VM Temurin-21.0.8+9 (build 21.0.8+9-LTS, mixed mode, sharing)
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> where.exe java
C:\Users\milads\AppData\Local\Programs\Eclipse Adoptium\jdk-21.0.8.9-hotspot\bin\java.exe
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> # Set JAVA_HOME (User)
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> $jdk = "C:\Users\milads\AppData\Local\Programs\Eclipse Adoptium\jdk-21.0.8.9-hotspot"
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> [Environment]::SetEnvironmentVariable("JAVA_HOME", $jdk, "User")
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> 
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> # Append JDK\bin to User PATH if not already present
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> $pUser = [Environment]::GetEnvironmentVariable("Path", "User")
(venv) PS C:\Users\milads\Documents\code\pyterrier_enterprise> if (-not ($pUser -split ';' | Where-Object { $_ -eq "$jdk\bin" })) {
>>   [Environment]::SetEnvironmentVariable("Path", "$pUser;$jdk\bin", "User")


#step1 build bm25 index 
C:\Users\milads\Documents\code\pyterrier_enterprise\.venv311\Lib\site-packages\tika\__init__.py:20: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated forC:\Users\milads\Documents\code\pyterrier_enterprise\.venv311\Lib\site-packages\tika\__init__.py:20: UserWarning: pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html. The pkg_resources package is slated for removal as early as 2025-11-30. Refrain from using this package or pin to Setuptools<81.
Java started and loaded: pyterrier.java, pyterrier.terrier.java [version=5.11 (build: craig.macdonald 2025-01-13 21:29), helper_version=0.0.8]
Indexing into: Z:\wccontainer\terrier_index
17:21:46.568 [main] WARN org.terrier.structures.indexing.Indexer -- Adding an empty document to the index (Z:\wccontainer\doc_urls\10073395_TC_QPF_talk072007.ppt) - further warnings are suppressed       
13:40:55.305 [main] WARN org.terrier.structures.indexing.Indexer -- Indexed 2111 empty documents
Index complete.
IndexRef: <org.terrier.querying.IndexRef at 0x1a3c697e570 jclass=org/terrier/querying/IndexRef jself=<LocalRef obj=0x-1b40349e at 0x1a3c68be8d0>>
(.venv311) PS C:\Users\milads\Documents\code\pyterrier_enterprise>


#step 2 make qrels and query sets

#step 3 sampling and runningpython -m src.sample_and_eval --index "Z:\wccontainer\terrier_index" --map ".\runs\query_id_map.tsv" --qrels ".\runs\targets.qrels" --n 5 --k 10 --metrics nDCG@10 P@10 --run_out ".\runs\sample_bm25.trec" --metrics_out ".\runs\sample_metrics.csv"   --tag BM25s\Documents\code\pyterrier_enterprise>
Java started and loaded: pyterrier.java, pyterrier.terrier.java [version=5.11 (build: craig.macdonald 2025-01-13 21:29), helper_version=0.0.8]
Sampled queries (qid → query):
  53215983509864 → iso iec jtc1 sc2 wg2 meeting 65 n5020
  132152850218032 → constitution of the socialist federal republic of yugoslavia 1963 doc
  127812383155076 → topoletraj doc
  7255701450059 → wywiad agen
  110222446301330 → kolasa che mno trials
pt.Experiment: 100%|███████████████████████████████████████████| 1/1 [01:46<00:00, 106.23s/system]
=== Sample & Eval Summary ===
Sampled queries : 5
Index           : Z:\wccontainer\terrier_index
Run             : runs\sample_bm25.trec
Metrics CSV     : runs\sample_metrics.csv
name  nDCG@10  P@10
BM25 0.110686  0.06