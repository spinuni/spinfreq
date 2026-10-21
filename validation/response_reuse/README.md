# Prepared modal response: accuracy and measured reuse

`spinfreq.ModalResponse` prepares a complete damped eigenbasis once and reuses
its inverse for subsequent drives and frequency grids. Each returned field is
checked against the original shifted linear system. Preparation and queries
remain dense; this does not remove the large-array memory limit.

One measured 201-point sweep from 1 to 45 GHz used the same independently
relaxed 20 × 20-cell skyrmion, 2 nm cells, bond DMI, 40 × 40 × 1 nm size,
and 1 microtesla z drive in both methods. The material is saved in the JSON.

| Operation | CPU time (s) | Wall time (s) |
| --- | --- | --- |
| Prepare full modal basis and inverse factorization | 0.8115 | 0.8117 |
| Query all 201 frequencies using that basis | 0.3233 | 0.3233 |
| Existing direct response, including its matrix assembly and shifted solves | 9.1633 | 9.1815 |

Including preparation, the measured CPU ratio is **8.07×**. Reusing an already
prepared basis gives **28.34×** for this sweep. These are single measurements
on this cloud CPU with one BLAS thread, not performance guarantees. No speed
threshold is used as a correctness gate.

The relative full-field difference between the two implementations is
**2.38e−12**, and the largest true shifted-system residual is **3.25e−11**.
The numerical gate is 1e−7 for both. This compares implementations on the same
operator; independent OOMMF physics validation is documented separately.
`mean_response.csv` contains complex mean responses from both implementations.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python benchmarks/response_reuse.py --check --output results/response-reuse
```

The public [usage guide](../../docs/guides/USAGE.md#7-forced-response-in-frequency-space)
shows repeated queries and exact linear transients under a raised-cosine drive
ramp. Rebuild the prepared object when the physical model or equilibrium
changes. Truncated mode sets are not accepted by this API.
