# WordNet Data Source

The author's [Etymological Wordnet project page](http://etym.org/) links to the
[2013-02-08 TSV archive](http://etym.org/etymwn-20130208.zip). The earlier Rutgers
download URL now returns 404. The author's archive is served over HTTP.

Extract `etymwn.tsv` to `data/raw/etymologies.tsv`, preserving the archive and its
`readme.txt` alongside it for provenance. `data/raw/` is ignored by Git.

The archive retrieved for the audit has these SHA-256 checksums. They pin
the bytes used for this project's audit; they are not an author-signed integrity
guarantee:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `etymwn-20130208.zip` | 27,504,275 | `7a046f01069945dfdc82be4173dd36ea5bda71758082af47dfc020d48d44d018` |
| `etymwn.tsv` | 313,273,677 | `361b946fa306732357b3ee375ea01ccdcbe3db1676898c47c39a92fb9861f7da` |

Run the [data audit](../docs/data-audit.md) to preserve the assertions and record
the input checksum with each analysis. Recheck provenance before substituting a
different download or dataset version.

The accompanying [readme.txt file](./data_source_readme.txt) contains the source author's license and other information.

[Information about metadata can be found here](http://lexvo.org/linkeddata/resources.html).
