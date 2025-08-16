'use client';

import { useState } from 'react';
import { useInventoryItems, useCriticalStock } from '@/hooks/use-inventory';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { formatCurrency, formatNumber, formatDate, getCategoryColor } from '@/lib/utils';
import { 
  ChartBarIcon, 
  DocumentArrowDownIcon, 
  CalendarDaysIcon,
  ExclamationTriangleIcon,
  CubeIcon,
  BuildingStorefrontIcon,
  ClipboardDocumentListIcon
} from '@heroicons/react/24/outline';

type ReportType = 'inventory-summary' | 'critical-stock' | 'warehouse-stock' | 'product-valuation';

export default function ReportsPage() {
  const [activeReport, setActiveReport] = useState<ReportType>('inventory-summary');
  const [dateRange, setDateRange] = useState({
    from: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0], // 30 days ago
    to: new Date().toISOString().split('T')[0] // today
  });

  const { data: inventoryData } = useInventoryItems({ page_size: 1000 });
  const { data: criticalStock } = useCriticalStock();
  const { data: productsData } = useProducts({ page_size: 1000 });
  const { data: warehousesData } = useWarehouses({ page_size: 100 });

  const reports = [
    {
      id: 'inventory-summary',
      name: 'Inventory Summary',
      icon: CubeIcon,
      description: 'Overall inventory overview with totals and categories'
    },
    {
      id: 'critical-stock',
      name: 'Critical Stock Report',
      icon: ExclamationTriangleIcon,
      description: 'Items below critical stock levels'
    },
    {
      id: 'warehouse-stock',
      name: 'Warehouse Stock Report',
      icon: BuildingStorefrontIcon,
      description: 'Stock levels by warehouse location'
    },
    {
      id: 'product-valuation',
      name: 'Product Valuation Report',
      icon: ClipboardDocumentListIcon,
      description: 'Product-wise inventory valuation with FIFO costs'
    }
  ];

  // Calculate summary statistics
  const totalInventoryValue = inventoryData?.items?.reduce((sum, item) => sum + item.total_cost, 0) || 0;
  const totalItems = inventoryData?.total || 0;
  const criticalItemsCount = criticalStock?.length || 0;
  const activeWarehouses = warehousesData?.items?.filter(w => w.is_active).length || 0;

  // Group inventory by category
  const inventoryByCategory = inventoryData?.items?.reduce((acc, item) => {
    const category = item.product?.category || 'UNKNOWN';
    if (!acc[category]) {
      acc[category] = { items: 0, value: 0 };
    }
    acc[category].items += 1;
    acc[category].value += item.total_cost;
    return acc;
  }, {} as Record<string, { items: number; value: number }>) || {};

  // Group inventory by warehouse
  const inventoryByWarehouse = inventoryData?.items?.reduce((acc, item) => {
    const warehouseName = item.warehouse?.name || 'Unknown';
    if (!acc[warehouseName]) {
      acc[warehouseName] = { items: 0, value: 0, quantity: 0 };
    }
    acc[warehouseName].items += 1;
    acc[warehouseName].value += item.total_cost;
    acc[warehouseName].quantity += item.available_quantity;
    return acc;
  }, {} as Record<string, { items: number; value: number; quantity: number }>) || {};

  const exportToCSV = (data: any[], filename: string) => {
    if (data.length === 0) return;

    const headers = Object.keys(data[0]).join(',');
    const csvContent = [
      headers,
      ...data.map(row => Object.values(row).map(value => `"${value}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${filename}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
  };

  const exportInventorySummary = () => {
    const data = Object.entries(inventoryByCategory).map(([category, stats]) => ({
      Category: category.replace('_', ' '),
      'Item Count': stats.items,
      'Total Value': formatCurrency(stats.value)
    }));
    exportToCSV(data, 'inventory_summary');
  };

  const exportCriticalStock = () => {
    if (!criticalStock) return;
    const data = criticalStock.map(item => ({
      'Product Code': item.product?.code,
      'Product Name': item.product?.name,
      'Category': item.product?.category?.replace('_', ' '),
      'Warehouse': item.warehouse?.name,
      'Available Quantity': item.available_quantity,
      'Critical Level': item.product?.critical_stock_level,
      'Unit Cost': formatCurrency(item.unit_cost),
      'Total Value': formatCurrency(item.total_cost)
    }));
    exportToCSV(data, 'critical_stock_report');
  };

  const exportWarehouseStock = () => {
    const data = Object.entries(inventoryByWarehouse).map(([warehouse, stats]) => ({
      Warehouse: warehouse,
      'Item Count': stats.items,
      'Total Quantity': formatNumber(stats.quantity),
      'Total Value': formatCurrency(stats.value)
    }));
    exportToCSV(data, 'warehouse_stock_report');
  };

  const exportProductValuation = () => {
    if (!inventoryData?.items) return;
    const data = inventoryData.items.map(item => ({
      'Product Code': item.product?.code,
      'Product Name': item.product?.name,
      'Category': item.product?.category?.replace('_', ' '),
      'Warehouse': item.warehouse?.name,
      'Available Quantity': item.available_quantity,
      'Unit Cost': formatCurrency(item.unit_cost),
      'Total Value': formatCurrency(item.total_cost),
      'Entry Date': formatDate(item.entry_date),
      'Batch Number': item.batch_number || 'N/A'
    }));
    exportToCSV(data, 'product_valuation_report');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Reports & Analytics</h1>
        <p className="mt-2 text-sm text-gray-700">
          Comprehensive reporting with real-time inventory data and FIFO cost analysis
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CubeIcon className="h-8 w-8 text-indigo-600" />
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">Total Items</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {formatNumber(totalItems, 0)}
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
                <dt className="text-sm font-medium text-gray-500 truncate">Critical Items</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {formatNumber(criticalItemsCount, 0)}
                </dd>
              </dl>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <BuildingStorefrontIcon className="h-8 w-8 text-green-600" />
            </div>
            <div className="ml-5 w-0 flex-1">
              <dl>
                <dt className="text-sm font-medium text-gray-500 truncate">Active Warehouses</dt>
                <dd className="text-lg font-medium text-gray-900">
                  {formatNumber(activeWarehouses, 0)}
                </dd>
              </dl>
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <CalendarDaysIcon className="h-8 w-8 text-purple-600" />
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

      {/* Report Navigation */}
      <div className="bg-white shadow rounded-lg">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6">
            {reports.map((report) => {
              const isActive = activeReport === report.id;
              return (
                <button
                  key={report.id}
                  onClick={() => setActiveReport(report.id as ReportType)}
                  className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                    isActive
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <report.icon className="h-5 w-5" />
                  <span>{report.name}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Report Content */}
        <div className="p-6">
          {/* Date Range Filter */}
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center space-x-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">From</label>
                <input
                  type="date"
                  value={dateRange.from}
                  onChange={(e) => setDateRange({ ...dateRange, from: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">To</label>
                <input
                  type="date"
                  value={dateRange.to}
                  onChange={(e) => setDateRange({ ...dateRange, to: e.target.value })}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
            </div>

            <div className="flex space-x-2">
              {activeReport === 'inventory-summary' && (
                <button
                  onClick={exportInventorySummary}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                >
                  <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                  Export CSV
                </button>
              )}
              {activeReport === 'critical-stock' && (
                <button
                  onClick={exportCriticalStock}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700"
                >
                  <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                  Export CSV
                </button>
              )}
              {activeReport === 'warehouse-stock' && (
                <button
                  onClick={exportWarehouseStock}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
                >
                  <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                  Export CSV
                </button>
              )}
              {activeReport === 'product-valuation' && (
                <button
                  onClick={exportProductValuation}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-purple-600 hover:bg-purple-700"
                >
                  <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                  Export CSV
                </button>
              )}
            </div>
          </div>

          {/* Inventory Summary Report */}
          {activeReport === 'inventory-summary' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Inventory Summary by Category</h3>
              <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                <table className="min-w-full divide-y divide-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Category
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Item Count
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Value
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Percentage
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {Object.entries(inventoryByCategory).map(([category, stats]) => (
                      <tr key={category}>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getCategoryColor(category)}`}>
                            {category.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatNumber(stats.items, 0)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatCurrency(stats.value)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatNumber((stats.value / totalInventoryValue) * 100, 1)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Critical Stock Report */}
          {activeReport === 'critical-stock' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Critical Stock Items</h3>
              {criticalStock && criticalStock.length > 0 ? (
                <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                  <table className="min-w-full divide-y divide-gray-300">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Product
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Warehouse
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Available
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Critical Level
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Value at Risk
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {criticalStock.map((item) => (
                        <tr key={item.id} className="bg-red-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <div className="text-sm font-medium text-gray-900">{item.product?.name}</div>
                              <div className="text-sm text-gray-500">Code: {item.product?.code}</div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {item.warehouse?.name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-red-600 font-medium">
                            {formatNumber(item.available_quantity)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatNumber(item.product?.critical_stock_level || 0)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatCurrency(item.total_cost)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No Critical Stock Items</h3>
                  <p className="mt-1 text-sm text-gray-500">All items are above critical stock levels.</p>
                </div>
              )}
            </div>
          )}

          {/* Warehouse Stock Report */}
          {activeReport === 'warehouse-stock' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Stock Levels by Warehouse</h3>
              <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                <table className="min-w-full divide-y divide-gray-300">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Warehouse
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Item Count
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Quantity
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Total Value
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {Object.entries(inventoryByWarehouse).map(([warehouse, stats]) => (
                      <tr key={warehouse}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {warehouse}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatNumber(stats.items, 0)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatNumber(stats.quantity)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {formatCurrency(stats.value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Product Valuation Report */}
          {activeReport === 'product-valuation' && (
            <div className="space-y-6">
              <h3 className="text-lg font-medium text-gray-900">Product Valuation with FIFO Costs</h3>
              {inventoryData?.items && inventoryData.items.length > 0 ? (
                <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
                  <table className="min-w-full divide-y divide-gray-300">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Product
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Warehouse
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Quantity
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          FIFO Unit Cost
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Total Value
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Entry Date
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {inventoryData.items.slice(0, 50).map((item) => (
                        <tr key={item.id}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div>
                              <div className="text-sm font-medium text-gray-900">{item.product?.name}</div>
                              <div className="text-sm text-gray-500">Code: {item.product?.code}</div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {item.warehouse?.name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatNumber(item.available_quantity)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatCurrency(item.unit_cost)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                            {formatCurrency(item.total_cost)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {formatDate(item.entry_date)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12">
                  <ChartBarIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">No Inventory Data</h3>
                  <p className="mt-1 text-sm text-gray-500">No inventory items found for valuation.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}