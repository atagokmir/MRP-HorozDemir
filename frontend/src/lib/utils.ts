import { clsx, type ClassValue } from 'clsx';
import { format, parseISO } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatCurrency(amount: number, currency = 'TRY'): string {
  return new Intl.NumberFormat('tr-TR', {
    style: 'currency',
    currency: currency,
  }).format(amount);
}

export function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat('tr-TR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatDate(dateString: string, formatPattern = 'dd/MM/yyyy'): string {
  try {
    const date = parseISO(dateString);
    return format(date, formatPattern);
  } catch {
    return dateString;
  }
}

export function formatDateTime(dateString: string): string {
  return formatDate(dateString, 'dd/MM/yyyy HH:mm');
}

export function getCategoryColor(category: string): string {
  const colors = {
    RAW_MATERIALS: 'bg-blue-100 text-blue-800',
    SEMI_FINISHED: 'bg-yellow-100 text-yellow-800',
    FINISHED_PRODUCTS: 'bg-green-100 text-green-800',
    PACKAGING: 'bg-purple-100 text-purple-800',
  };
  return colors[category as keyof typeof colors] || 'bg-gray-100 text-gray-800';
}

export function getStatusColor(status: string): string {
  const colors = {
    PENDING: 'bg-yellow-100 text-yellow-800',
    APPROVED: 'bg-green-100 text-green-800',
    REJECTED: 'bg-red-100 text-red-800',
    QUARANTINE: 'bg-orange-100 text-orange-800',
    IN: 'bg-green-100 text-green-800',
    OUT: 'bg-red-100 text-red-800',
    ADJUSTMENT: 'bg-blue-100 text-blue-800',
    TRANSFER: 'bg-purple-100 text-purple-800',
  };
  return colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-800';
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(null, args), wait);
  };
}

export function handleAPIError(error: any): string {
  if (error?.response?.message) {
    return error.response.message;
  }
  if (error?.message) {
    return error.message;
  }
  return 'An unexpected error occurred';
}