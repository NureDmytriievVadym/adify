import { categories } from './catalog.ts';

export type ListingSort = 'newest' | 'oldest' | 'price_asc' | 'price_desc';
export type ListingTypeValue = 'offer' | 'request';

export interface ListingFilters {
  q: string;
  type?: ListingTypeValue;
  category?: string;
  priceMin: string;
  priceMax: string;
  deliveryMax: string;
  ageMin: string;
  ageMax: string;
  country: string;
  socioeconomic: string;
  traits: string[];
  sort: ListingSort;
}

export const SORT_OPTIONS: { value: ListingSort; label: string }[] = [
  { value: 'newest', label: 'Newest first' },
  { value: 'oldest', label: 'Oldest first' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
];

export const emptyFilters = (): ListingFilters => ({
  q: '',
  priceMin: '',
  priceMax: '',
  deliveryMax: '',
  ageMin: '',
  ageMax: '',
  country: '',
  socioeconomic: '',
  traits: [],
  sort: 'newest',
});

const text = (value: string | null, max = 100) => (value ?? '').trim().slice(0, max);
const digits = (value: string | null, max: number) => {
  const match = /^\d{1,3}$/.exec((value ?? '').trim());
  return match && Number(match[0]) <= max ? match[0] : '';
};
const money = (value: string | null) => {
  const raw = (value ?? '').trim();
  return /^\d{1,8}(\.\d{1,2})?$/.test(raw) ? raw : '';
};

export function filtersFromParams(params: {
  get(name: string): string | null;
  getAll(name: string): string[];
}): ListingFilters {
  const filters = emptyFilters();
  const type = params.get('type');
  const category = params.get('category');
  const sort = params.get('sort');
  filters.q = text(params.get('q'));
  filters.type = type === 'offer' || type === 'request' ? type : undefined;
  filters.category = categories.some((item) => item.id === category) ? category! : undefined;
  filters.priceMin = money(params.get('price_min'));
  filters.priceMax = money(params.get('price_max'));
  filters.deliveryMax = digits(params.get('delivery_max'), 365);
  filters.ageMin = digits(params.get('age_min'), 120);
  filters.ageMax = digits(params.get('age_max'), 120);
  filters.country = text(params.get('country'));
  filters.socioeconomic = text(params.get('socioeconomic'));
  filters.traits = params
    .getAll('traits')
    .map((trait) => text(trait, 50))
    .filter(Boolean)
    .slice(0, 20);
  filters.sort = SORT_OPTIONS.some((option) => option.value === sort)
    ? (sort as ListingSort)
    : 'newest';
  return filters;
}

/** Canonical query string; empty values and the default sort are omitted. */
export function paramsFromFilters(filters: ListingFilters): string {
  const params = new URLSearchParams();
  const set = (key: string, value: string | undefined) => {
    if (value) params.set(key, value);
  };
  set('q', filters.q.trim());
  set('type', filters.type);
  set('category', filters.category);
  set('price_min', filters.priceMin);
  set('price_max', filters.priceMax);
  set('delivery_max', filters.deliveryMax);
  set('age_min', filters.ageMin);
  set('age_max', filters.ageMax);
  set('country', filters.country.trim());
  set('socioeconomic', filters.socioeconomic.trim());
  for (const trait of filters.traits) {
    if (trait.trim()) params.append('traits', trait.trim());
  }
  if (filters.sort !== 'newest') set('sort', filters.sort);
  return params.toString();
}

export function activeFilterCount(filters: ListingFilters): number {
  let count = 0;
  if (filters.type) count += 1;
  if (filters.category) count += 1;
  if (filters.priceMin || filters.priceMax) count += 1;
  if (filters.deliveryMax) count += 1;
  if (filters.ageMin || filters.ageMax) count += 1;
  if (filters.country) count += 1;
  if (filters.socioeconomic) count += 1;
  if (filters.traits.length) count += 1;
  return count;
}

export function validateFilters(filters: ListingFilters): string | undefined {
  const min = Number(filters.priceMin || 0);
  const max = Number(filters.priceMax || Infinity);
  if (filters.priceMin && filters.priceMax && min > max) {
    return 'The minimum price cannot be greater than the maximum.';
  }
  const ageMin = Number(filters.ageMin || 0);
  const ageMax = Number(filters.ageMax || Infinity);
  if (filters.ageMin && filters.ageMax && ageMin > ageMax) {
    return 'The minimum age cannot be greater than the maximum.';
  }
  return undefined;
}
