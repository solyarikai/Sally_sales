/**
 * Location-to-Country mapping for Clay People data
 *
 * Clay's "Location" field often contains metro areas, cities, regions,
 * or non-English text instead of country names. This module normalizes
 * them to standard country names.
 *
 * Usage:
 *   const { toCountry } = require('./location_to_country');
 *   toCountry('Greater St. Louis') // → 'United States'
 *   toCountry('Metro Manila')      // → 'Philippines'
 *   toCountry('دبي الإمارات')       // → 'United Arab Emirates'
 */

const LOCATION_TO_COUNTRY = {
  // US metro areas / regions / states
  'greater st. louis': 'United States',
  'kansas city metropolitan area': 'United States',
  'missouri area': 'United States',
  'greater chicago area': 'United States',
  'new york city metropolitan area': 'United States',
  'new york metropolitan area': 'United States',
  'atlanta metropolitan area': 'United States',
  'san francisco bay area': 'United States',
  'greater minneapolis-st. paul area': 'United States',
  'dallas-fort worth metroplex': 'United States',
  'los angeles metropolitan area': 'United States',
  'denver metropolitan area': 'United States',
  'greater tampa bay area': 'United States',
  'greater phoenix area': 'United States',
  'greater houston': 'United States',
  'detroit metropolitan area': 'United States',
  'greater boston': 'United States',
  'washington dc-baltimore area': 'United States',
  'south carolina area': 'United States',
  'texas metropolitan area': 'United States',
  'oregon metropolitan area': 'United States',
  'greater indianapolis': 'United States',
  'greater cleveland': 'United States',
  'greater philadelphia': 'United States',
  'miami-fort lauderdale area': 'United States',
  'greater lexington area': 'United States',
  'oklahoma city metropolitan area': 'United States',
  'iowa city-cedar rapids area': 'United States',
  'little rock metropolitan area': 'United States',
  'joplin metropolitan area': 'United States',
  'greater milwaukee': 'United States',
  'omaha metropolitan area': 'United States',
  'des moines metropolitan area': 'United States',
  'ohio metropolitan area': 'United States',
  'boise metropolitan area': 'United States',
  'greater colorado springs area': 'United States',
  'peoria metropolitan area': 'United States',
  'greater tucson area': 'United States',
  'pensacola metropolitan area': 'United States',
  'grand rapids metropolitan area': 'United States',
  'kansas metropolitan area': 'United States',
  'blacksburg-christiansburg-radford area': 'United States',
  'ar area': 'United States',
  'baton rouge metropolitan area': 'United States',
  'greater chattanooga': 'United States',
  'greater wilmington area': 'United States',
  'greater eugene-springfield area': 'United States',
  'greater lansing': 'United States',
  'south carolina metropolitan area': 'United States',
  'greater kennewick area': 'United States',
  'greater richmond region': 'United States',
  'greensboro--winston-salem--high point area': 'United States',
  'greater reno area': 'United States',
  'greater evansville area': 'United States',
  'greater jackson area': 'United States',
  'greater hartford': 'United States',
  'greater orlando': 'United States',
  'maine metropolitan area': 'United States',
  'memphis metropolitan area': 'United States',
  'urbana-champaign area': 'United States',
  'greater columbus area': 'United States',
  'greater reading area': 'United States',
  'greater cincinnati': 'United States',
  'greater pittsburgh': 'United States',
  'nashville metropolitan area': 'United States',
  'charlotte metropolitan area': 'United States',

  // Canada
  'greater montreal metropolitan area': 'Canada',
  'greater ottawa metropolitan area': 'Canada',
  'greater toronto area': 'Canada',
  'greater vancouver metropolitan area': 'Canada',

  // Italy
  'italia': 'Italy',
  'greater modena metropolitan area': 'Italy',
  'italy metropolitan area': 'Italy',

  // Brazil
  'brasil': 'Brazil',
  'são paulo e região': 'Brazil',
  'bogotá d.c. metropolitan area': 'Colombia',

  // Philippines
  'metro manila': 'Philippines',

  // Australia
  'greater melbourne area': 'Australia',
  'greater sydney area': 'Australia',
  'greater brisbane area': 'Australia',
  'greater perth area': 'Australia',

  // India
  'greater delhi area': 'India',
  'greater hyderabad area': 'India',
  'mumbai metropolitan region': 'India',

  // UK
  'greater cambridge area': 'United Kingdom',
  'greater derby area': 'United Kingdom',
  'greater sheffield area': 'United Kingdom',
  'greater leicester area': 'United Kingdom',

  // France
  'greater paris metropolitan region': 'France',

  // Germany
  'frankfurt/rhein-main': 'Germany',

  // Switzerland
  'schweiz': 'Switzerland',
  'greater zurich area': 'Switzerland',

  // Sweden
  'sverige': 'Sweden',

  // Spain
  'madrid y alrededores': 'Spain',

  // Belgium
  'brussels metropolitan area': 'Belgium',

  // Japan
  '日本 東京都': 'Japan',

  // Mexico
  'méxico': 'Mexico',
  'área metropolitana de ciudad de méxico': 'Mexico',
  'mexico city metropolitan area': 'Mexico',

  // Arabic locations
  'دبي الإمارات العربية المتحدة': 'United Arab Emirates',
  'الإمارات العربية المتحدة': 'United Arab Emirates',
  'الرياض السعودية': 'Saudi Arabia',
  'القاهرة مصر': 'Egypt',
  'الاسكندرية مصر': 'Egypt',
  'الدار البيضاء سطات المغرب': 'Morocco',
  'ولاية تونس تونس': 'Tunisia',

  // Turkey
  'türkiye': 'Turkey',

  // Netherlands
  'nederland': 'Netherlands',

  // Ukraine
  'kyiv metropolitan area': 'Ukraine',

  // Luxembourg
  'luxembourg': 'Luxembourg',

  // Israel
  'israel': 'Israel',

  // New Zealand
  'new zealand': 'New Zealand',

  // Gibraltar
  'gibraltar': 'Gibraltar',

  // Czechia
  'czechia': 'Czech Republic',
};

/**
 * Convert a Clay location string to a country name.
 * @param {string} location - Raw location from Clay (e.g. "San Francisco Bay Area")
 * @returns {string} - Country name, or original location if no mapping found
 */
function toCountry(location) {
  if (!location) return 'Unknown';

  const normalized = location.toLowerCase().trim();

  // Direct match
  if (LOCATION_TO_COUNTRY[normalized]) {
    return LOCATION_TO_COUNTRY[normalized];
  }

  // Check if it's already a known country name
  const knownCountries = new Set([
    'united states', 'india', 'united kingdom', 'pakistan', 'italy', 'philippines',
    'canada', 'australia', 'nigeria', 'colombia', 'united arab emirates', 'france',
    'kyrgyzstan', 'argentina', 'brazil', 'kenya', 'south africa', 'north macedonia',
    'cameroon', 'spain', 'mexico', 'switzerland', 'portugal', 'singapore', 'ukraine',
    'ireland', 'bangladesh', 'serbia', 'egypt', 'belgium', 'japan', 'zambia', 'greece',
    'kosovo', 'democratic republic of the congo', 'poland', 'croatia', 'china',
    'germany', 'zimbabwe', 'tanzania', 'finland', 'netherlands', 'denmark', 'sri lanka',
    'estonia', 'iran', 'libya', 'austria', 'sweden', 'new zealand', 'algeria',
    'ethiopia', 'honduras', 'albania', 'venezuela', 'uzbekistan', 'afghanistan',
    'romania', 'costa rica', 'belize', 'lebanon', 'turkey', 'saudi arabia', 'nepal',
    'bahrain', 'chile', 'el salvador', 'ecuador', 'peru', 'uruguay', 'cyprus',
    'morocco', 'norway', 'south korea', 'thailand', 'indonesia', 'vietnam',
    'hungary', 'bulgaria', 'slovakia', 'slovenia', 'latvia', 'lithuania',
    'malta', 'iceland', 'georgia', 'armenia', 'azerbaijan', 'kazakhstan',
    'tajikistan', 'turkmenistan', 'mongolia', 'myanmar', 'cambodia', 'laos',
    'brunei', 'papua new guinea', 'fiji', 'somalia', 'sudan', 'south sudan',
    'mali', 'niger', 'chad', 'burkina faso', 'guinea', 'senegal', 'ghana',
    'togo', 'benin', 'sierra leone', 'liberia', 'ivory coast', 'rwanda',
    'burundi', 'malawi', 'mozambique', 'madagascar', 'mauritius', 'botswana',
    'namibia', 'eswatini', 'lesotho', 'angola', 'gabon', 'congo',
    'central african republic', 'equatorial guinea', 'eritrea', 'djibouti',
    'comoros', 'cape verde', 'tunisia', 'jordan', 'iraq', 'syria', 'yemen',
    'oman', 'kuwait', 'qatar', 'palestine', 'palestinian authority',
  ]);

  if (knownCountries.has(normalized)) {
    // Capitalize properly
    return location.trim();
  }

  // Fuzzy match: check if any key is contained in the location
  for (const [key, country] of Object.entries(LOCATION_TO_COUNTRY)) {
    if (normalized.includes(key) || key.includes(normalized)) {
      return country;
    }
  }

  // US state detection (last resort)
  const usStates = [
    'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
    'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
    'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
    'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
    'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
    'new hampshire', 'new jersey', 'new mexico', 'new york', 'north carolina',
    'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania',
    'rhode island', 'south carolina', 'south dakota', 'tennessee', 'texas',
    'utah', 'vermont', 'virginia', 'washington', 'west virginia',
    'wisconsin', 'wyoming', 'district of columbia',
  ];

  for (const state of usStates) {
    if (normalized.includes(state)) return 'United States';
  }

  return location.trim(); // Return as-is if no mapping
}

/**
 * Check if a location is in the United States
 */
function isUS(location) {
  return toCountry(location) === 'United States';
}

module.exports = { toCountry, isUS, LOCATION_TO_COUNTRY };
