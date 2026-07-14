export function getMasonryColumnCount(viewportWidth: number) {
  if (viewportWidth <= 760) return 2;
  if (viewportWidth <= 1040) return 3;
  if (viewportWidth <= 1380) return 4;
  return 5;
}

export function distributeAcrossColumns<T>(
  items: readonly T[],
  columnCount: number,
) {
  const safeColumnCount = Math.max(1, Math.floor(columnCount));
  const columns = Array.from({ length: safeColumnCount }, () => [] as T[]);

  items.forEach((item, index) => {
    columns[index % safeColumnCount]?.push(item);
  });

  return columns;
}
