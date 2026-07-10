import matplotlib.pyplot as plt
import numpy as np

queries = ["Q1\nTextual", "Q2\nTextual excl.", "Q3\nOrden", "Q4\nAgg section", "Q5\nAgg news_paper"]
mongo = [5.29, 336.63, 3.03, 36.18, 35.33]
citus = [5.00, 558.16, 20.00, 8.00, 9.00]

x = np.arange(len(queries))
w = 0.38

fig, ax = plt.subplots(figsize=(10, 5.5))
b1 = ax.bar(x - w/2, mongo, w, label="MongoDB (Sharding)", color="#4E79A7")
b2 = ax.bar(x + w/2, citus, w, label="Citus (PostgreSQL)", color="#59A14F")

ax.set_yscale("log")
ax.set_ylabel("Tiempo de ejecucion (ms) - escala logaritmica")
ax.set_title("Comparacion de tiempos Q1-Q5: MongoDB vs Citus")
ax.set_xticks(x)
ax.set_xticklabels(queries)
ax.legend()
ax.grid(axis="y", ls="--", alpha=0.4)

for bars in (b1, b2):
    for r in bars:
        h = r.get_height()
        ax.annotate(f"{h:.1f}", (r.get_x() + r.get_width()/2, h),
                    textcoords="offset points", xytext=(0, 3),
                    ha="center", fontsize=8)

plt.tight_layout()
plt.savefig("comparacion/comparacion_q1q5.png", dpi=150)
print("Grafico guardado en comparacion/comparacion_q1q5.png")
