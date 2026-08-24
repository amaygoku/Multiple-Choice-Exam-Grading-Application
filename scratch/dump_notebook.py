import json

nb = json.load(open('viet_Tay.ipynb', 'r', encoding='utf-8'))
out = open('scratch/viet_tay_cells.txt', 'w', encoding='utf-8')

for i, cell in enumerate(nb['cells']):
    out.write(f"=== Cell {i} ({cell['cell_type']}) ===\n")
    out.write(''.join(cell['source']) + "\n")
    out.write("-" * 60 + "\n")

out.close()
print("Done writing notebook cells!")
