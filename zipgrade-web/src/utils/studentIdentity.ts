export function normalizeStudentName(value: string) {
  return (value || '')
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function isStudentNameMatch(inputName: string, databaseName: string) {
  const input = normalizeStudentName(inputName);
  const database = normalizeStudentName(databaseName);
  return !!input && !!database && input === database;
}
