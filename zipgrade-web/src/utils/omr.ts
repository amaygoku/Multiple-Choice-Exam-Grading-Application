import { AnswerOption } from '../types';

/**
 * Optical Mark Recognition (OMR) Utility
 * This simplified version uses canvas pixel sampling to detect filled bubbles.
 */

export const BUBBLE_THRESHOLD = 0.5; // Sensitivity for detecting a "filled" bubble

export interface BubbleCoordinate {
  question: number;
  option: AnswerOption;
  x: number; // percentage width
  y: number; // percentage height
}

// Fixed coordinates for a 20-question sheet (example layout)
// In a real app, these would be generated based on a template.
export const generateCoordinates = (numQuestions: number): BubbleCoordinate[] => {
  const coords: BubbleCoordinate[] = [];
  const options: AnswerOption[] = ['A', 'B', 'C', 'D', 'E'];
  const cols = numQuestions > 10 ? 2 : 1;
  const rows = numQuestions / cols;

  for (let q = 1; q <= numQuestions; q++) {
    const col = q > rows ? 1 : 0;
    const row = (q - 1) % rows;
    
    options.forEach((opt, optIdx) => {
      coords.push({
        question: q,
        option: opt,
        x: 15 + col * 45 + optIdx * 6, // columns at 15% and 60%
        y: 10 + row * 4,             // rows starting at 10%
      });
    });
  }
  return coords;
};

export const detectBubbles = (
  ctx: CanvasRenderingContext2D,
  width: number,
  height: number,
  coords: BubbleCoordinate[]
): Record<number, AnswerOption | null> => {
  const results: Record<number, AnswerOption | null> = {};
  const questionScores: Record<number, { opt: AnswerOption; density: number }[]> = {};

  coords.forEach((coord) => {
    const px = (coord.x / 100) * width;
    const py = (coord.y / 100) * height;
    const radius = 5; // Scan radius

    // Sample pixels in a small square around the bubble
    const imgData = ctx.getImageData(px - radius, py - radius, radius * 2, radius * 2);
    const data = imgData.data;
    let darkPixels = 0;

    for (let i = 0; i < data.length; i += 4) {
      const r = data[i];
      const g = data[i + 1];
      const b = data[i + 2];
      // Simple grayscale & threshold
      const brightness = (r + g + b) / 3;
      if (brightness < 120) darkPixels++; // Hardcoded threshold for "dark"
    }

    const density = darkPixels / (imgData.width * imgData.height);
    
    if (!questionScores[coord.question]) questionScores[coord.question] = [];
    questionScores[coord.question].push({ opt: coord.option, density });
  });

  // For each question, find the bubble with the highest density above threshold
  Object.keys(questionScores).forEach((qStr) => {
    const q = parseInt(qStr);
    const options = questionScores[q];
    const best = options.reduce((prev, curr) => (curr.density > prev.density ? curr : prev));
    
    if (best.density > BUBBLE_THRESHOLD) {
      results[q] = best.opt;
    } else {
      results[q] = null;
    }
  });

  return results;
};
