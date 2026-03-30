#!/usr/bin/env python3
"""Convert apartment plan PNG into vector SVG using OpenCV."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import List

import cv2
import numpy as np


@dataclass(frozen=True)
class Config:
    input_png: Path
    output_svg: Path
    scale_ratio: float
    dpi: float
    min_area_px: float
    epsilon_ratio: float
    threshold_block_size: int
    threshold_c: int
    invert: bool
    stroke_width_m: float


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description=(
            "Legge una planimetria PNG ed esporta contorni vettoriali in SVG "
            "con coordinate scalate in metri reali."
        )
    )
    parser.add_argument("input_png", type=Path, help="File PNG di input")
    parser.add_argument("output_svg", type=Path, help="File SVG di output")
    parser.add_argument(
        "--scale",
        type=float,
        default=200.0,
        help="Rapporto di scala (default: 200 per scala 1:200)",
    )
    parser.add_argument(
        "--dpi",
        type=float,
        default=300.0,
        help="DPI immagine usato per convertire pixel->metri (default: 300)",
    )
    parser.add_argument(
        "--min-area-px",
        type=float,
        default=250.0,
        help="Area minima in pixel per tenere un contorno (default: 250)",
    )
    parser.add_argument(
        "--epsilon-ratio",
        type=float,
        default=0.002,
        help="Semplificazione contorni Douglas-Peucker (default: 0.002)",
    )
    parser.add_argument(
        "--threshold-block-size",
        type=int,
        default=31,
        help="Block size soglia adattiva (dispari, default: 31)",
    )
    parser.add_argument(
        "--threshold-c",
        type=int,
        default=2,
        help="Parametro C soglia adattiva (default: 2)",
    )
    parser.add_argument(
        "--stroke-width-m",
        type=float,
        default=0.02,
        help="Spessore tratto SVG in metri reali (default: 0.02)",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Inverte bianco/nero prima dell'estrazione contorni",
    )

    args = parser.parse_args()

    if args.threshold_block_size % 2 == 0 or args.threshold_block_size < 3:
        parser.error("--threshold-block-size deve essere dispari e >= 3")
    if args.scale <= 0:
        parser.error("--scale deve essere > 0")
    if args.dpi <= 0:
        parser.error("--dpi deve essere > 0")
    if args.epsilon_ratio < 0:
        parser.error("--epsilon-ratio deve essere >= 0")
    if args.stroke_width_m <= 0:
        parser.error("--stroke-width-m deve essere > 0")

    return Config(
        input_png=args.input_png,
        output_svg=args.output_svg,
        scale_ratio=args.scale,
        dpi=args.dpi,
        min_area_px=args.min_area_px,
        epsilon_ratio=args.epsilon_ratio,
        threshold_block_size=args.threshold_block_size,
        threshold_c=args.threshold_c,
        invert=args.invert,
        stroke_width_m=args.stroke_width_m,
    )


def pixel_to_real_meter_factor(scale_ratio: float, dpi: float) -> float:
    return (0.0254 / dpi) * scale_ratio


def preprocess(image_gray: np.ndarray, cfg: Config) -> np.ndarray:
    blurred = cv2.GaussianBlur(image_gray, (5, 5), 0)
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        cfg.threshold_block_size,
        cfg.threshold_c,
    )

    if cfg.invert:
        binary = cv2.bitwise_not(binary)

    kernel = np.ones((3, 3), dtype=np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    return binary


def extract_polylines(binary: np.ndarray, cfg: Config) -> List[np.ndarray]:
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    polylines: List[np.ndarray] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < cfg.min_area_px:
            continue

        peri = cv2.arcLength(contour, True)
        epsilon = cfg.epsilon_ratio * peri
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 2:
            continue

        polylines.append(approx.reshape(-1, 2))

    polylines.sort(key=lambda p: cv2.contourArea(p.reshape(-1, 1, 2)), reverse=True)
    return polylines


def export_svg(
    polylines: List[np.ndarray],
    output_svg: Path,
    meters_per_pixel: float,
    image_width: int,
    image_height: int,
    stroke_width_m: float,
) -> int:
    output_svg.parent.mkdir(parents=True, exist_ok=True)

    width_m = image_width * meters_per_pixel
    height_m = image_height * meters_per_pixel

    lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            f'viewBox="0 0 {width_m:.6f} {height_m:.6f}" '
            f'width="{width_m:.6f}m" height="{height_m:.6f}m">'
        ),
        f'  <g fill="none" stroke="#000000" stroke-width="{stroke_width_m:.6f}">',
    ]

    for poly in polylines:
        points = [
            f"{(float(p[0]) * meters_per_pixel):.6f},{(float(p[1]) * meters_per_pixel):.6f}"
            for p in poly
        ]
        if len(poly) > 2:
            lines.append(f'    <polygon points="{" ".join(points)}" />')
        else:
            lines.append(f'    <polyline points="{" ".join(points)}" />')

    lines.append("  </g>")
    lines.append("</svg>")

    output_svg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(polylines)


def main() -> int:
    cfg = parse_args()
    if not cfg.input_png.exists():
        raise FileNotFoundError(f"File input non trovato: {cfg.input_png}")

    image = cv2.imread(str(cfg.input_png), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Impossibile leggere il PNG: {cfg.input_png}")

    binary = preprocess(image, cfg)
    polylines = extract_polylines(binary, cfg)
    meters_per_pixel = pixel_to_real_meter_factor(cfg.scale_ratio, cfg.dpi)

    count = export_svg(
        polylines,
        cfg.output_svg,
        meters_per_pixel,
        image.shape[1],
        image.shape[0],
        cfg.stroke_width_m,
    )

    print(f"Contorni estratti: {count}")
    print(f"SVG creato: {cfg.output_svg}")
    print(f"Scala usata: 1:{cfg.scale_ratio:g}, DPI: {cfg.dpi:g}")
    print(f"Fattore conversione: 1 px = {meters_per_pixel:.6f} m reali")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
