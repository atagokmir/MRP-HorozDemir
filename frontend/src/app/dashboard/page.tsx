'use client';

import Link from 'next/link';
import { useCriticalStock, useInventoryItems } from '@/hooks/use-inventory';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { formatCurrency, formatNumber, getCategoryColor } from '@/lib/utils';
import {
  ExclamationTriangleIcon,
  CubeIcon,
  BuildingStorefrontIcon,
  ClipboardDocumentListIcon,
  TruckIcon,
} from '@heroicons/react/24/outline';

export default function DashboardPage() {
  const { data: criticalStock, isLoading: criticalLoading } = useCriticalStock();
  const { data: inventoryData, isLoading: inventoryLoading } = useInventoryItems({ page_size: 50 });
  const { data: productsData, isLoading: productsLoading } = useProducts({ page_size: 10 });
  const { data: warehousesData, isLoading: warehousesLoading } = useWarehouses({ page_size: 10 });

  const stats = [
    {
      name: 'Total Products',
      value: productsData?.total || 0,
      icon: ClipboardDocumentListIcon,
      href: '/products',
      loading: productsLoading,
    },
    {
      name: 'Active Warehouses',
      value: warehousesData?.items?.filter(w => w.is_active).length || 0,
      icon: BuildingStorefrontIcon,
      href: '/warehouses',
      loading: warehousesLoading,
    },
    {
      name: 'Inventory Items',
      value: inventoryData?.total || 0,
      icon: CubeIcon,
      href: '/inventory',
      loading: inventoryLoading,
    },
    {
      name: 'Critical Stock Items',
      value: criticalStock?.length || 0,
      icon: ExclamationTriangleIcon,
      href: '/inventory?filter=critical',
      loading: criticalLoading,
      color: 'text-red-600',
    },
  ];

  const totalInventoryValue = inventoryData?.items?.reduce((sum, item) => sum + item.total_cost, 0) || 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-sm text-gray-700">
          Welcome to the Horoz Demir MRP System. Here&apos;s an overview of your operations.
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Link
            key={stat.name}
            href={stat.href}
            className="relative bg-white pt-5 px-4 pb-12 sm:pt-6 sm:px-6 shadow rounded-lg overflow-hidden hover:shadow-md transition-shadow"
          >
            <div>
              <div className="absolute bg-indigo-500 rounded-md p-3">
                <stat.icon className={`h-6 w-6 text-white ${stat.color || ''}`} />
              </div>
              <p className="ml-16 text-sm font-medium text-gray-500 truncate">
                {stat.name}
              </p>
              <p className="ml-16 text-2xl font-semibold text-gray-900">
                {stat.loading ? (
                  <span className="animate-pulse">...</span>
                ) : (
                  formatNumber(stat.value, 0)
                )}
              </p>
            </div>
          </Link>
        ))}
      </div>

      {/* Total Inventory Value */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Financial Overview</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="border-l-4 border-indigo-500 pl-4">
            <p className="text-sm font-medium text-gray-500">Total Inventory Value</p>
            <p className="text-2xl font-semibold text-gray-900">
              {inventoryLoading ? (
                <span className="animate-pulse">Loading...</span>
              ) : (
                formatCurrency(totalInventoryValue)
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Critical Stock Alert */}
      {criticalStock && criticalStock.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center">
            <ExclamationTriangleIcon className="h-6 w-6 text-red-600 mr-2" />
            <h2 className="text-lg font-medium text-red-800">Critical Stock Alert</h2>
          </div>
          <p className="text-sm text-red-700 mt-2 mb-4">
            The following items are below critical stock levels:
          </p>
          <div className="space-y-2 mb-4">
            {criticalStock.slice(0, 5).map((item) => (
              <div key={item.id} className="flex items-center justify-between bg-white p-3 rounded border">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{item.product?.name}</p>
                  <p className="text-sm text-gray-500">
                    Warehouse: {item.warehouse?.name} | 
                    Current: {formatNumber(item.available_quantity)} | 
                    Critical Level: {formatNumber(item.product?.critical_stock_level || 0)}
                  </p>
                </div>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${getCategoryColor(item.product?.category || '')}`}>
                  {item.product?.category}
                </span>
              </div>
            ))}
            {criticalStock.length > 5 && (
              <p className="text-sm text-red-600">
                ...and {criticalStock.length - 5} more items
              </p>
            )}
          </div>
          <Link
            href="/inventory?filter=critical"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700"
          >
            View All Critical Items
          </Link>
        </div>
      )}

      {/* Recent Products */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Recent Products</h2>
            <Link
              href="/products"
              className="text-sm font-medium text-indigo-600 hover:text-indigo-500"
            >
              View all
            </Link>
          </div>
        </div>
        <div className="px-6 py-4">
          {productsLoading ? (
            <div className="animate-pulse space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-4 bg-gray-200 rounded"></div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {productsData?.items?.slice(0, 5).map((product) => (
                <div key={product.id} className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{product.name}</p>
                    <p className="text-sm text-gray-500">Code: {product.code}</p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getCategoryColor(product.category)}`}>
                      {product.category}
                    </span>
                    <span className="text-sm text-gray-500">{product.unit_of_measure}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}