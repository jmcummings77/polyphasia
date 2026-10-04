# Portfolio figures

These presentation figures read the unchanged [full-corpus analysis](../../reports/20130208/README.md)
and [synthetic query benchmark](../../reports/benchmarks/README.md). Rendering does
not rerun the corpus analysis or the benchmark.

- [Transformation attrition](transformation-attrition.png) counts retained and
  excluded assertion records under each direction policy.
- [Projection comparison](projection-comparison.png) compares English ancestry,
  root-family context, and weak components, including added and omitted labels.
- [Runtime and memory scaling](runtime-memory-scaling.png) shows recorded medians
  and minimum–maximum bands for two synthetic query workloads. Process peak RSS
  includes imports and warmup; it is not incremental algorithm memory.

The [rendering manifest](manifest.json) records input and renderer SHA-256 hashes,
rendering-library versions, and the size and hash of each PNG. It is separate from
the original corpus run manifest. Reproduction uses a new output directory:

```sh
uv run --frozen --extra analysis python -m scripts.build_portfolio_figures \
  --analysis reports/20130208 \
  --benchmark reports/benchmarks/query-benchmark.json \
  --output data/processed/portfolio-figures
```

The two corpus figures derive from Gerard de Melo's Etymological WordNet
2013-02-08, primarily extracted from English Wiktionary. Its **CC-BY-SA 3.0**
terms apply to these data-derived figures; see the [source attribution](../../data/data_source_readme.txt)
and [reuse statement](../../reports/20130208/README.md#source-and-reuse).
The benchmark figure uses generated synthetic inputs. The renderer is covered by
the repository's [MIT code license](../../LICENSE).
