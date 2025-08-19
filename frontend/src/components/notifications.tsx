'use client';

import { useState, useEffect } from 'react';
import { useCriticalStock } from '@/hooks/use-inventory';
import { formatNumber, getCategoryColor } from '@/lib/utils';
import { 
  BellIcon, 
  ExclamationTriangleIcon, 
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';
import Link from 'next/link';

interface NotificationCenterProps {
  className?: string;
}

export function NotificationCenter({ className = '' }: NotificationCenterProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: criticalStock, isLoading } = useCriticalStock();

  const criticalCount = criticalStock?.length || 0;
  const hasNotifications = criticalCount > 0;

  return (
    <div className={`relative inline-block ${className}`}>
      {/* Notification Bell */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-indigo-200 hover:text-white focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 rounded-full"
        title={hasNotifications ? `${criticalCount} critical stock alerts` : 'No notifications'}
      >
        <BellIcon className="h-6 w-6" />
        {hasNotifications && (
          <span className="absolute top-0 right-0 block h-3 w-3 rounded-full bg-red-500 ring-2 ring-white" />
        )}
      </button>

      {/* Notification Dropdown */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none z-50">
          <div className="py-1">
            {/* Header */}
            <div className="px-4 py-3 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-gray-900">
                  Notifications {hasNotifications && `(${criticalCount})`}
                </h3>
                <button
                  onClick={() => setIsOpen(false)}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="max-h-96 overflow-y-auto">
              {isLoading ? (
                <div className="px-4 py-6 text-center">
                  <div className="animate-pulse text-sm text-gray-500">Loading notifications...</div>
                </div>
              ) : !hasNotifications ? (
                <div className="px-4 py-6 text-center">
                  <BellIcon className="mx-auto h-8 w-8 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-500">No critical stock alerts</p>
                </div>
              ) : (
                <div className="divide-y divide-gray-100">
                  {/* Critical Stock Alert Header */}
                  <div className="px-4 py-3">
                    <div className="flex items-center">
                      <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mr-2" />
                      <span className="text-sm font-medium text-red-800">
                        Critical Stock Alert
                      </span>
                    </div>
                    <p className="text-xs text-red-600 mt-1">
                      {criticalCount} item{criticalCount !== 1 ? 's' : ''} below critical level
                    </p>
                  </div>

                  {/* Critical Items List */}
                  <div className="py-2">
                    {criticalStock?.slice(0, isExpanded ? undefined : 3).map((item) => (
                      <div key={item.id} className="px-4 py-2 hover:bg-gray-50">
                        <div className="flex items-start space-x-3">
                          <ExclamationTriangleIcon className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-900 truncate">
                              {item.product?.name}
                            </p>
                            <div className="flex items-center space-x-2 mt-1">
                              <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getCategoryColor(item.product?.category || '')}`}>
                                {item.product?.category?.replace('_', ' ')}
                              </span>
                            </div>
                            <div className="text-xs text-gray-500 mt-1">
                              <div>Available: {formatNumber(item.available_quantity)} | 
                                Critical: {formatNumber(item.product?.critical_stock_level || 0)}</div>
                              <div>Warehouse: {item.warehouse?.name}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}

                    {/* Show More/Less Toggle */}
                    {criticalStock && criticalStock.length > 3 && (
                      <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="w-full px-4 py-2 text-left text-sm text-indigo-600 hover:text-indigo-500 hover:bg-gray-50 flex items-center"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronDownIcon className="h-4 w-4 mr-1" />
                            Show less
                          </>
                        ) : (
                          <>
                            <ChevronRightIcon className="h-4 w-4 mr-1" />
                            Show {criticalStock.length - 3} more items
                          </>
                        )}
                      </button>
                    )}
                  </div>

                  {/* Action Buttons */}
                  <div className="px-4 py-3 bg-gray-50">
                    <div className="flex space-x-2">
                      <Link
                        href="/dashboard/inventory?filter=critical"
                        className="flex-1 text-center px-3 py-2 text-xs font-medium text-white bg-red-600 rounded hover:bg-red-700"
                        onClick={() => setIsOpen(false)}
                      >
                        View All Critical Items
                      </Link>
                      <Link
                        href="/dashboard/stock-operations"
                        className="flex-1 text-center px-3 py-2 text-xs font-medium text-indigo-600 bg-white border border-indigo-600 rounded hover:bg-indigo-50"
                        onClick={() => setIsOpen(false)}
                      >
                        Stock Operations
                      </Link>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Toast Notification Component for Real-time Alerts
interface ToastNotificationProps {
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  isVisible: boolean;
  onClose: () => void;
  autoClose?: boolean;
  duration?: number;
}

export function ToastNotification({ 
  message, 
  type, 
  isVisible, 
  onClose, 
  autoClose = true, 
  duration = 5000 
}: ToastNotificationProps) {
  useEffect(() => {
    if (isVisible && autoClose) {
      const timer = setTimeout(() => {
        onClose();
      }, duration);

      return () => clearTimeout(timer);
    }
  }, [isVisible, autoClose, duration, onClose]);

  if (!isVisible) return null;

  const getTypeStyles = () => {
    switch (type) {
      case 'success':
        return 'bg-green-100 border-green-500 text-green-700';
      case 'error':
        return 'bg-red-100 border-red-500 text-red-700';
      case 'warning':
        return 'bg-yellow-100 border-yellow-500 text-yellow-700';
      case 'info':
        return 'bg-blue-100 border-blue-500 text-blue-700';
      default:
        return 'bg-gray-100 border-gray-500 text-gray-700';
    }
  };

  const getIcon = () => {
    switch (type) {
      case 'success':
        return '✓';
      case 'error':
        return '✕';
      case 'warning':
        return '⚠';
      case 'info':
        return 'ℹ';
      default:
        return '';
    }
  };

  return (
    <div className={`fixed top-4 right-4 z-50 max-w-sm w-full border-l-4 p-4 rounded shadow-lg ${getTypeStyles()}`}>
      <div className="flex items-center">
        <span className="text-lg mr-2">{getIcon()}</span>
        <div className="flex-1">
          <p className="text-sm font-medium">{message}</p>
        </div>
        <button
          onClick={onClose}
          className="ml-4 text-gray-400 hover:text-gray-600"
        >
          <XMarkIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

// Hook for managing toast notifications
export function useToast() {
  const [toasts, setToasts] = useState<Array<{
    id: string;
    message: string;
    type: 'success' | 'error' | 'warning' | 'info';
  }>>([]);

  const showToast = (message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, message, type }]);
  };

  const hideToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  return {
    toasts,
    showToast,
    hideToast,
  };
}