from vietocr.tool.config import Cfg

config = Cfg.load_config_from_name('vgg_seq2seq')
vocab = config['vocab']

with open('scratch/vietocr_vocab.txt', 'w', encoding='utf-8') as f:
    f.write(f"Size: {len(vocab)}\n")
    f.write(vocab + "\n")

print("Done!")
