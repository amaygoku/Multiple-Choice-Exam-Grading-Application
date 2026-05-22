import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf


def build_datasets(dataset_dir, image_size, batch_size):
    dataset_dir = Path(dataset_dir)
    train_dir = dataset_dir / "train"
    val_dir = dataset_dir / "val"
    test_dir = dataset_dir / "test"

    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="binary",
        color_mode="rgb",
        image_size=(image_size, image_size),
        batch_size=batch_size,
        shuffle=True,
        seed=42,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        val_dir,
        labels="inferred",
        label_mode="binary",
        color_mode="rgb",
        image_size=(image_size, image_size),
        batch_size=batch_size,
        shuffle=False,
    )
    test_ds = tf.keras.utils.image_dataset_from_directory(
        test_dir,
        labels="inferred",
        label_mode="binary",
        color_mode="rgb",
        image_size=(image_size, image_size),
        batch_size=batch_size,
        shuffle=False,
    )

    class_names = train_ds.class_names
    train_ds = train_ds.prefetch(tf.data.AUTOTUNE)
    val_ds = val_ds.prefetch(tf.data.AUTOTUNE)
    test_ds = test_ds.prefetch(tf.data.AUTOTUNE)
    return train_ds, val_ds, test_ds, class_names


def compute_class_weights(train_dir):
    counts = {}
    total = 0
    for class_index, class_name in enumerate(sorted(p.name for p in Path(train_dir).iterdir() if p.is_dir())):
        count = len(list((Path(train_dir) / class_name).glob("*.png")))
        counts[class_index] = count
        total += count

    class_weights = {}
    num_classes = len(counts)
    for class_index, count in counts.items():
        class_weights[class_index] = total / max(count * num_classes, 1)
    return counts, class_weights


def build_model(image_size, learning_rate, dropout, pretrained):
    data_augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomRotation(0.03),
            tf.keras.layers.RandomZoom(0.08),
            tf.keras.layers.RandomTranslation(0.04, 0.04),
            tf.keras.layers.RandomContrast(0.08),
        ],
        name="augment",
    )

    weights = "imagenet" if pretrained else None
    try:
        backbone = tf.keras.applications.MobileNetV3Small(
            input_shape=(image_size, image_size, 3),
            include_top=False,
            weights=weights,
            pooling="avg",
        )
    except Exception:
        backbone = tf.keras.applications.MobileNetV3Small(
            input_shape=(image_size, image_size, 3),
            include_top=False,
            weights=None,
            pooling="avg",
        )

    backbone.trainable = False
    inputs = tf.keras.Input(shape=(image_size, image_size, 3))
    x = data_augmentation(inputs)
    x = tf.keras.applications.mobilenet_v3.preprocess_input(x)
    x = backbone(x, training=False)
    x = tf.keras.layers.Dropout(dropout)(x)
    outputs = tf.keras.layers.Dense(1, activation="sigmoid")(x)
    model = tf.keras.Model(inputs, outputs)

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ],
    )
    return model, backbone


def unfreeze_and_finetune(model, backbone, learning_rate):
    backbone.trainable = True
    for layer in backbone.layers[:-20]:
        layer.trainable = False
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.BinaryAccuracy(name="accuracy"),
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ],
    )


def evaluate_and_save(model, test_ds, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics = model.evaluate(test_ds, return_dict=True)
    y_true = []
    y_prob = []
    for images, labels in test_ds:
        probs = model.predict(images, verbose=0).reshape(-1)
        y_prob.extend(probs.tolist())
        y_true.extend(labels.numpy().reshape(-1).astype(int).tolist())

    y_pred = [1 if prob >= 0.5 else 0 for prob in y_prob]

    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)

    report = {
        "metrics": {key: float(value) for key, value in metrics.items()},
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "samples": len(y_true),
    }
    (output_dir / "test_metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Train MobileNetV3Small binary classifier on Kaggle-ready OMR cells.")
    parser.add_argument("--dataset-dir", required=True, help="Path to task folder containing train/val/test")
    parser.add_argument("--output-dir", default="/kaggle/working/mobilenet_run")
    parser.add_argument("--image-size", type=int, default=96)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs-head", type=int, default=8)
    parser.add_argument("--epochs-finetune", type=int, default=6)
    parser.add_argument("--learning-rate-head", type=float, default=1e-3)
    parser.add_argument("--learning-rate-finetune", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--pretrained", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_ds, val_ds, test_ds, class_names = build_datasets(args.dataset_dir, args.image_size, args.batch_size)
    train_counts, class_weights = compute_class_weights(Path(args.dataset_dir) / "train")

    model, backbone = build_model(args.image_size, args.learning_rate_head, args.dropout, args.pretrained)

    callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=3, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.5, patience=2),
        tf.keras.callbacks.ModelCheckpoint(
            filepath=str(output_dir / "best_model.keras"),
            monitor="val_loss",
            save_best_only=True,
        ),
    ]

    history_head = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs_head,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1,
    )

    if args.epochs_finetune > 0:
        unfreeze_and_finetune(model, backbone, args.learning_rate_finetune)
        history_finetune = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=args.epochs_finetune,
            callbacks=callbacks,
            class_weight=class_weights,
            verbose=1,
        )
    else:
        history_finetune = None

    report = evaluate_and_save(model, test_ds, output_dir)
    model.save(output_dir / "final_model.keras")

    history_payload = {
        "class_names": class_names,
        "train_counts": train_counts,
        "class_weights": class_weights,
        "head": history_head.history,
        "finetune": history_finetune.history if history_finetune else None,
        "test_report": report,
    }
    (output_dir / "history.json").write_text(json.dumps(history_payload, indent=2), encoding="utf-8")
    print(json.dumps(history_payload["test_report"], indent=2))


if __name__ == "__main__":
    main()
