export function stepCarouselIndex(
  currentIndex: number,
  step: -1 | 1,
  imageCount: number,
): number {
  if (imageCount <= 1) return 0;
  return Math.min(imageCount - 1, Math.max(0, currentIndex + step));
}
