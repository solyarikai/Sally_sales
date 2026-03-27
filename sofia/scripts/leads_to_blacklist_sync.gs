/**
 * OnSocial LEADS → Blacklist Auto-Sync
 *
 * Автоматически находит ВСЕ листы со словом "LEADS" в названии,
 * собирает Company Website + Company Name,
 * и добавляет новые компании в Exclusion List (Blacklist).
 *
 * Также синхронизирует лист BLACKLIST внутри основной таблицы.
 *
 * Установка:
 * 1. Открой OnSocial <> Sally → Extensions → Apps Script
 * 2. Вставь этот код
 * 3. Запусти syncLeadsToBlacklist() вручную один раз (даст запрос на permissions)
 * 4. Настрой триггер: Edit → Triggers → Add Trigger
 *    - Function: syncLeadsToBlacklist
 *    - Event source: Time-driven
 *    - Type: Hour timer → Every hour (или как удобно)
 */

// === КОНФИГУРАЦИЯ ===
const SOURCE_SPREADSHEET_ID = '1ImSKJFuZtUVYqWPBQYQ1Xo8KOzA9rHVCmWSCg2wXB1E'; // OnSocial <> Sally
const BLACKLIST_SPREADSHEET_ID = '1drDBlOBr_BEeYd0Fv5292IbAfdTApLgITOht6PZHCU4'; // Exclusion List - Blacklist

// Префикс для поиска листов с лидами (exact case: "LEADS")
const LEADS_PREFIX = 'LEADS';

// Индексы колонок в LEADS (0-based)
const COL_COMPANY_WEBSITE = 4; // E
const COL_COMPANY_NAME = 5;    // F
const COL_EMAIL = 7;           // H

// === ОСНОВНАЯ ФУНКЦИЯ ===
function syncLeadsToBlacklist() {
  const source = SpreadsheetApp.openById(SOURCE_SPREADSHEET_ID);
  const blacklistSpreadsheet = SpreadsheetApp.openById(BLACKLIST_SPREADSHEET_ID);

  // 1. Собираем все компании из LEADS
  const leadsCompanies = collectLeadsCompanies(source);
  Logger.log(`Найдено ${leadsCompanies.size} уникальных компаний в LEADS`);

  // 2. Синхронизируем с внешним Blacklist (Exclusion Lists)
  const addedToExclusion = syncToExclusionList(blacklistSpreadsheet, leadsCompanies);
  Logger.log(`Добавлено ${addedToExclusion} новых компаний в Exclusion Lists`);

  // 3. Синхронизируем с внутренним BLACKLIST листом
  const addedToBlacklist = syncToInternalBlacklist(source, leadsCompanies);
  Logger.log(`Добавлено ${addedToBlacklist} новых компаний в BLACKLIST`);

  // 4. Лог
  const summary = `[${new Date().toISOString()}] Sync: ${leadsCompanies.size} companies total, +${addedToExclusion} to Exclusion List, +${addedToBlacklist} to BLACKLIST`;
  Logger.log(summary);

  return summary;
}

// === ПОИСК ЛИСТОВ С ЛИДАМИ ===
function findLeadsSheets(spreadsheet) {
  const allSheets = spreadsheet.getSheets();
  const leadsSheets = [];

  for (const sheet of allSheets) {
    const name = sheet.getName();
    if (name.startsWith(LEADS_PREFIX)) {
      leadsSheets.push(name);
    }
  }

  Logger.log(`Найдено ${leadsSheets.length} листов с лидами: ${leadsSheets.join(', ')}`);
  return leadsSheets;
}

// === СБОР КОМПАНИЙ ИЗ LEADS ===
function collectLeadsCompanies(spreadsheet) {
  // Map: normalized website → {name, website, emails[]}
  const companies = new Map();
  const leadsSheets = findLeadsSheets(spreadsheet);

  for (const sheetName of leadsSheets) {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (!sheet) continue;

    const data = sheet.getDataRange().getValues();
    if (data.length < 2) continue; // Пустой лист или только заголовок

    // Проверяем что структура колонок совпадает (Company Website в E, Company Name в F)
    const header = data[0];
    const hasExpectedStructure =
      (header[COL_COMPANY_WEBSITE] || '').toString().toLowerCase().includes('website') ||
      (header[COL_COMPANY_NAME] || '').toString().toLowerCase().includes('company');

    if (!hasExpectedStructure) {
      Logger.log(`Лист "${sheetName}" — структура колонок не совпадает, пропускаю`);
      continue;
    }

    // Пропускаем заголовок (строка 1)
    for (let i = 1; i < data.length; i++) {
      const row = data[i];
      const website = normalizeWebsite(row[COL_COMPANY_WEBSITE]);
      const name = (row[COL_COMPANY_NAME] || '').toString().trim();
      const email = (row[COL_EMAIL] || '').toString().trim();

      if (!website && !name) continue; // Пустая строка

      const key = website || name.toLowerCase();

      if (!companies.has(key)) {
        companies.set(key, {
          name: name,
          website: website,
          emails: []
        });
      }

      if (email) {
        companies.get(key).emails.push(email);
      }
    }
  }

  return companies;
}

// === СИНХРОНИЗАЦИЯ С EXCLUSION LIST (внешняя таблица) ===
function syncToExclusionList(blacklistSpreadsheet, leadsCompanies) {
  const sheet = blacklistSpreadsheet.getSheetByName('Exclusion Lists');
  if (!sheet) {
    Logger.log('Лист "Exclusion Lists" не найден!');
    return 0;
  }

  // Читаем существующие записи
  const existingData = sheet.getDataRange().getValues();
  const existingWebsites = new Set();
  const existingNames = new Set();

  for (let i = 1; i < existingData.length; i++) {
    const name = (existingData[i][0] || '').toString().trim().toLowerCase();
    const website = normalizeWebsite(existingData[i][1]);
    if (website) existingWebsites.add(website);
    if (name) existingNames.add(name);
  }

  // Находим новые компании
  const newRows = [];
  for (const [key, company] of leadsCompanies) {
    const websiteExists = company.website && existingWebsites.has(company.website);
    const nameExists = company.name && existingNames.has(company.name.toLowerCase());

    if (!websiteExists && !nameExists) {
      newRows.push([company.name, company.website]);
    }
  }

  // Добавляем новые строки
  if (newRows.length > 0) {
    const lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, newRows.length, 2).setValues(newRows);
  }

  return newRows.length;
}

// === СИНХРОНИЗАЦИЯ С ВНУТРЕННИМ BLACKLIST ===
function syncToInternalBlacklist(spreadsheet, leadsCompanies) {
  const sheet = spreadsheet.getSheetByName('BLACKLIST');
  if (!sheet) {
    Logger.log('Лист "BLACKLIST" не найден!');
    return 0;
  }

  // Читаем существующие записи (колонка B = Company Website)
  const existingData = sheet.getDataRange().getValues();
  const existingWebsites = new Set();

  for (let i = 1; i < existingData.length; i++) {
    const website = normalizeWebsite(existingData[i][1]);
    if (website) existingWebsites.add(website);
  }

  // Находим новые
  const newRows = [];
  let nextNumber = existingData.length; // Следующий номер (№)

  for (const [key, company] of leadsCompanies) {
    if (company.website && !existingWebsites.has(company.website)) {
      newRows.push([nextNumber, company.website]);
      nextNumber++;
    }
  }

  // Добавляем
  if (newRows.length > 0) {
    const lastRow = sheet.getLastRow();
    sheet.getRange(lastRow + 1, 1, newRows.length, 2).setValues(newRows);
  }

  return newRows.length;
}

// === УТИЛИТЫ ===
function normalizeWebsite(value) {
  if (!value) return '';
  let website = value.toString().trim().toLowerCase();
  // Убираем протокол и www
  website = website.replace(/^https?:\/\//, '').replace(/^www\./, '');
  // Убираем trailing slash
  website = website.replace(/\/+$/, '');
  return website;
}

// === МЕНЮ (опционально) ===
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🔄 Blacklist Sync')
    .addItem('Sync Now', 'syncLeadsToBlacklist')
    .addItem('Setup Hourly Trigger', 'createHourlyTrigger')
    .addItem('Remove All Triggers', 'removeAllTriggers')
    .addToUi();
}

function createHourlyTrigger() {
  // Удаляем старые триггеры этой функции
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'syncLeadsToBlacklist') {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  // Создаём новый триггер — каждый час
  ScriptApp.newTrigger('syncLeadsToBlacklist')
    .timeBased()
    .everyHours(1)
    .create();

  SpreadsheetApp.getUi().alert('✅ Триггер создан: синхронизация каждый час');
}

function removeAllTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'syncLeadsToBlacklist') {
      ScriptApp.deleteTrigger(trigger);
    }
  }
  SpreadsheetApp.getUi().alert('✅ Все триггеры синхронизации удалены');
}
