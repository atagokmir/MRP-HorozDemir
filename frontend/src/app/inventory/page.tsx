'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useInventoryItems, useCriticalStock } from '@/hooks/use-inventory';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { InventoryItem, ProductCategory, WarehouseType, QualityStatus } from '@/types/api';
import { formatCurrency, formatNumber, formatDate, getCategoryColor, getStatusColor, handleAPIError, debounce } from '@/lib/utils';
import { 
  MagnifyingGlassIcon, 
  ExclamationTriangleIcon, 
  CubeIcon,
  CalendarDaysIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  FunnelIcon
} from '@heroicons/react/24/outline';
import Link from 'next/link';

export default function InventoryPage() {
  const router = useRouter();
  const [searchTerm, setSearchTerm] = useState('');
  const [productFilter, setProductFilter] = useState<number | ''>('');
  const [warehouseFilter, setWarehouseFilter] = useState<number | ''>('');
  const [categoryFilter, setCategoryFilter] = useState<ProductCategory | ''>('');
  const [statusFilter, setStatusFilter] = useState<QualityStatus | ''>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [showCriticalOnly, setShowCriticalOnly] = useState(false);
  const [sortBy, setSortBy] = useState<'name' | 'quantity' | 'value' | 'date'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Check URL params for critical filter
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('filter') === 'critical') {
      setShowCriticalOnly(true);
    }
  }, []);

  const debouncedSearch = debounce((value: string) => {
    setSearchTerm(value);
    setCurrentPage(1);
  }, 300);

  const { data: inventoryData, isLoading: inventoryLoading, error } = useInventoryItems({
    page: currentPage,
    page_size: 25,
    search: searchTerm || undefined,
    product_id: productFilter || undefined,
    warehouse_id: warehouseFilter || undefined,
    quality_status: statusFilter || undefined,
  });

  const { data: criticalStock } = useCriticalStock();
  const { data: productsData } = useProducts({ page_size: 1000 });
  const { data: warehousesData } = useWarehouses({ page_size: 100 });

  // Filter critical items if needed
  const displayItems = showCriticalOnly && criticalStock 
    ? criticalStock.filter(item => {
        if (searchTerm) {
          const searchLower = searchTerm.toLowerCase();
          return item.product?.name.toLowerCase().includes(searchLower) ||
                 item.product?.code.toLowerCase().includes(searchLower);
        }
        if (productFilter) return item.product_id === productFilter;
        if (warehouseFilter) return item.warehouse_id === warehouseFilter;
        if (categoryFilter) return item.product?.category === categoryFilter;
        if (statusFilter) return item.quality_status === statusFilter;
        return true;
      })
    : inventoryData?.items || [];

  // Sort items
  const sortedItems = [...displayItems].sort((a, b) => {
    let aValue: any, bValue: any;
    
    switch (sortBy) {
      case 'name':
        aValue = a.product?.name || '';
        bValue = b.product?.name || '';
        break;
      case 'quantity':
        aValue = a.available_quantity;
        bValue = b.available_quantity;
        break;
      case 'value':
        aValue = a.total_cost;
        bValue = b.total_cost;
        break;
      case 'date':
        aValue = new Date(a.entry_date);
        bValue = new Date(b.entry_date);
        break;
      default:
        return 0;
    }

    if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
    if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
    return 0;
  });

  const handleSort = (field: typeof sortBy) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  const getSortIcon = (field: typeof sortBy) => {
    if (sortBy !== field) return null;
    return sortOrder === 'asc' ? 
      <ArrowUpIcon className="h-4 w-4" /> : 
      <ArrowDownIcon className="h-4 w-4" />;
  };

  const totalInventoryValue = sortedItems.reduce((sum, item) => sum + item.total_cost, 0);
  const lowStockItems = sortedItems.filter(item => 
    item.available_quantity <= (item.product?.critical_stock_level || 0)
  ).length;

  if (error) {
    return <div className="text-red-600">Error: {handleAPIError(error)}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Inventory Management</h1>
          <p className="mt-2 text-sm text-gray-700">
            Track stock levels, costs, and FIFO batches across all warehouses
          </p>
        </div>
        <div className="flex space-x-3">
          <Link
            href="/stock-operations"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <CubeIcon className="h-4 w-4 mr-2" />
            Stock Operations
          </Link>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CubeIcon className="h-8 w-8 text-indigo-600" />
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">Total Items</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {inventoryLoading ? '...' : formatNumber(inventoryData?.total || 0, 0)}
                </dd>
              </dl>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <ExclamationTriangleIcon className="h-8 w-8 text-red-600" />
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">Low Stock Items</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {formatNumber(lowStockItems, 0)}
                </dd>
              </dl>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CalendarDaysIcon className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">Total Value</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {formatCurrency(totalInventoryValue)}
                </dd>
              </dl>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white p-6 rounded-lg shadow space-y-4">
        <div className="flex items-center space-x-2">
          <FunnelIcon className="h-5 w-5 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900">Filters</h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {/* Search */}
          <div className="lg:col-span-2">
            <div className="relative">
              <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search products..."
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                onChange={(e) => debouncedSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Product Filter */}
          <div>
            <select
              value={productFilter}
              onChange={(e) => {
                setProductFilter(e.target.value ? Number(e.target.value) : '');
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">All Products</option>
              {productsData?.items?.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </div>

          {/* Warehouse Filter */}
          <div>
            <select
              value={warehouseFilter}
              onChange={(e) => {
                setWarehouseFilter(e.target.value ? Number(e.target.value) : '');
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">All Warehouses</option>
              {warehousesData?.items?.map((warehouse) => (
                <option key={warehouse.id} value={warehouse.id}>
                  {warehouse.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as QualityStatus | '');
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="">All Status</option>
              <option value="PENDING">Pending</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="QUARANTINE">Quarantine</option>
            </select>
          </div>

          {/* Critical Items Toggle */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="critical-only"
              checked={showCriticalOnly}
              onChange={(e) => setShowCriticalOnly(e.target.checked)}
              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            />
            <label htmlFor="critical-only" className="ml-2 text-sm text-gray-700">
              Critical Only
            </label>
          </div>
        </div>
      </div>

      {/* Inventory Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('name')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Product</span>
                    {getSortIcon('name')}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Warehouse
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('quantity')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Stock</span>
                    {getSortIcon('quantity')}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  FIFO Cost
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('value')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Total Value</span>
                    {getSortIcon('value')}
                  </div>
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('date')}
                >
                  <div className="flex items-center space-x-1">
                    <span>Entry Date</span>
                    {getSortIcon('date')}
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {inventoryLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center">
                    <div className="animate-pulse">Loading inventory...</div>
                  </td>
                </tr>
              ) : sortedItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-gray-500">
                    No inventory items found
                  </td>
                </tr>
              ) : (
                sortedItems.map((item) => {
                  const isCritical = item.available_quantity <= (item.product?.critical_stock_level || 0);
                  const isLowStock = item.available_quantity <= (item.product?.minimum_stock_level || 0);
                  
                  return (
                    <tr key={item.inventory_item_id || item.id} className={`hover:bg-gray-50 ${isCritical ? 'bg-red-50' : ''}`}>
                      <td className="px-6 py-4">
                        <div className="flex items-center">
                          {isCritical && (
                            <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mr-2" />
                          )}
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {item.product?.name}
                            </div>
                            <div className="text-sm text-gray-500">
                              Code: {item.product?.code}
                            </div>
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getCategoryColor(item.product?.category || '')}`}>
                              {item.product?.category?.replace('_', ' ')}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">{item.warehouse?.name}</div>
                        <div className="text-sm text-gray-500">{item.warehouse?.type?.replace('_', ' ')}</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="space-y-1">
                          <div className={`text-sm font-medium ${isCritical ? 'text-red-600' : isLowStock ? 'text-yellow-600' : 'text-gray-900'}`}>
                            Available: {formatNumber(item.available_quantity)}
                          </div>
                          <div className="text-sm text-gray-500">
                            Reserved: {formatNumber(item.reserved_quantity)}
                          </div>
                          <div className="text-sm text-gray-500">
                            Total: {formatNumber(item.quantity_in_stock)}
                          </div>
                          {item.product && (
                            <div className="text-xs text-gray-400">
                              Min: {formatNumber(item.product.minimum_stock_level)} | 
                              Critical: {formatNumber(item.product.critical_stock_level)}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900">
                          {formatCurrency(item.unit_cost)}
                        </div>
                        {item.batch_number && (
                          <div className="text-xs text-gray-500">
                            Batch: {item.batch_number}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-gray-900">
                          {formatCurrency(item.total_cost)}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(item.quality_status)}`}>
                          {item.quality_status}
                        </span>
                        {item.expiry_date && (
                          <div className="text-xs text-gray-500 mt-1">
                            Expires: {formatDate(item.expiry_date)}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDate(item.entry_date)}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination for non-critical view */}
        {!showCriticalOnly && inventoryData && inventoryData.total_pages > 1 && (
          <div className="bg-white px-6 py-3 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing {((currentPage - 1) * 25) + 1} to {Math.min(currentPage * 25, inventoryData.total)} of {inventoryData.total} results
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={!inventoryData.has_previous}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={!inventoryData.has_next}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}