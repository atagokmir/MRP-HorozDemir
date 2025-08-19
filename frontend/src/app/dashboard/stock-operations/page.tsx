'use client';

import { useState } from 'react';
import { useStockIn, useStockOut, useStockAdjustment, useStockAvailability } from '@/hooks/use-inventory';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { useSuppliers } from '@/hooks/use-suppliers';
import { StockInRequest, StockOutRequest, StockAdjustmentRequest, QualityStatus } from '@/types/api';
import { handleAPIError, formatCurrency, formatNumber } from '@/lib/utils';
import { 
  PlusIcon, 
  MinusIcon, 
  ArrowsUpDownIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

type OperationType = 'stock-in' | 'stock-out' | 'adjustment';

export default function StockOperationsPage() {
  const [activeTab, setActiveTab] = useState<OperationType>('stock-in');
  const [selectedProduct, setSelectedProduct] = useState<number | ''>('');
  const [selectedWarehouse, setSelectedWarehouse] = useState<number | ''>('');
  const [selectedSupplier, setSelectedSupplier] = useState<number | ''>('');
  
  // Stock In Form
  const [stockInData, setStockInData] = useState<Partial<StockInRequest>>({
    quantity: 0,
    unit_cost: 0,
    batch_number: '',
    quality_status: 'PENDING',
    entry_date: new Date().toISOString().split('T')[0],
    expiry_date: '',
    notes: '',
  });

  // Stock Out Form
  const [stockOutData, setStockOutData] = useState<Partial<StockOutRequest>>({
    quantity: 0,
    reference_type: '',
    reference_id: '',
    notes: '',
  });

  // Stock Adjustment Form
  const [adjustmentData, setAdjustmentData] = useState<Partial<StockAdjustmentRequest>>({
    adjustment_quantity: 0,
    reason: '',
    notes: '',
  });

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  // API Hooks
  const { data: productsData } = useProducts({ page_size: 1000 });
  const { data: warehousesData } = useWarehouses({ page_size: 100 });
  const { data: suppliersData } = useSuppliers({ page_size: 1000 });
  const { data: stockAvailability } = useStockAvailability(
    selectedProduct ? Number(selectedProduct) : 0,
    selectedWarehouse ? Number(selectedWarehouse) : undefined
  );

  const stockInMutation = useStockIn();
  const stockOutMutation = useStockOut();
  const adjustmentMutation = useStockAdjustment();

  const clearMessages = () => {
    setSuccessMessage('');
    setErrorMessage('');
  };

  const handleStockIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct || !selectedWarehouse) {
      setErrorMessage('Please select both product and warehouse');
      return;
    }

    setIsSubmitting(true);
    clearMessages();

    try {
      const data: StockInRequest = {
        product_id: Number(selectedProduct),
        warehouse_id: Number(selectedWarehouse),
        quantity: stockInData.quantity || 0,
        unit_cost: stockInData.unit_cost || 0,
        batch_number: stockInData.batch_number,
        supplier_id: selectedSupplier ? Number(selectedSupplier) : undefined,
        quality_status: stockInData.quality_status || 'PENDING',
        entry_date: stockInData.entry_date,
        expiry_date: stockInData.expiry_date || undefined,
        notes: stockInData.notes,
      };

      await stockInMutation.mutateAsync(data);
      setSuccessMessage(`Successfully added ${formatNumber(data.quantity)} units to stock`);
      
      // Reset form
      setStockInData({
        quantity: 0,
        unit_cost: 0,
        batch_number: '',
        quality_status: 'PENDING',
        entry_date: new Date().toISOString().split('T')[0],
        expiry_date: '',
        notes: '',
      });
      setSelectedSupplier('');
    } catch (error) {
      setErrorMessage(handleAPIError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStockOut = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct || !selectedWarehouse) {
      setErrorMessage('Please select both product and warehouse');
      return;
    }

    setIsSubmitting(true);
    clearMessages();

    try {
      const data: StockOutRequest = {
        product_id: Number(selectedProduct),
        warehouse_id: Number(selectedWarehouse),
        quantity: stockOutData.quantity || 0,
        reference_type: stockOutData.reference_type,
        reference_id: stockOutData.reference_id,
        notes: stockOutData.notes,
      };

      const result = await stockOutMutation.mutateAsync(data);
      
      setSuccessMessage(
        `Successfully removed ${formatNumber(data.quantity)} units from stock. ` +
        `Total cost: ${formatCurrency(result.total_cost)}`
      );
      
      // Reset form
      setStockOutData({
        quantity: 0,
        reference_type: '',
        reference_id: '',
        notes: '',
      });
    } catch (error) {
      setErrorMessage(handleAPIError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdjustment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProduct || !selectedWarehouse) {
      setErrorMessage('Please select both product and warehouse');
      return;
    }

    setIsSubmitting(true);
    clearMessages();

    try {
      const data: StockAdjustmentRequest = {
        product_id: Number(selectedProduct),
        warehouse_id: Number(selectedWarehouse),
        adjustment_quantity: adjustmentData.adjustment_quantity || 0,
        reason: adjustmentData.reason || '',
        notes: adjustmentData.notes,
      };

      await adjustmentMutation.mutateAsync(data);
      setSuccessMessage(
        `Successfully adjusted stock by ${formatNumber(data.adjustment_quantity, 2)} units`
      );
      
      // Reset form
      setAdjustmentData({
        adjustment_quantity: 0,
        reason: '',
        notes: '',
      });
    } catch (error) {
      setErrorMessage(handleAPIError(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  const tabs = [
    { id: 'stock-in', name: 'Stock In', icon: PlusIcon, color: 'text-green-600' },
    { id: 'stock-out', name: 'Stock Out', icon: MinusIcon, color: 'text-red-600' },
    { id: 'adjustment', name: 'Adjustment', icon: ArrowsUpDownIcon, color: 'text-blue-600' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Stock Operations</h1>
        <p className="mt-2 text-sm text-gray-700">
          Perform stock movements with automatic FIFO cost calculations
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id as OperationType);
                  clearMessages();
                }}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  isActive
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className={`h-5 w-5 ${isActive ? tab.color : 'text-gray-400'}`} />
                <span>{tab.name}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <div className="rounded-md bg-green-50 p-4">
          <div className="flex">
            <CheckCircleIcon className="h-5 w-5 text-green-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">{successMessage}</p>
            </div>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="rounded-md bg-red-50 p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm font-medium text-red-800">{errorMessage}</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form Section */}
        <div className="lg:col-span-2">
          <div className="bg-white shadow rounded-lg p-6">
            {/* Common Product and Warehouse Selection */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">Product *</label>
                <select
                  value={selectedProduct}
                  onChange={(e) => setSelectedProduct(e.target.value ? Number(e.target.value) : '')}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                >
                  <option value="">Select a product...</option>
                  {productsData?.items?.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name} ({product.code})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Warehouse *</label>
                <select
                  value={selectedWarehouse}
                  onChange={(e) => setSelectedWarehouse(e.target.value ? Number(e.target.value) : '')}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                >
                  <option value="">Select a warehouse...</option>
                  {warehousesData?.items?.map((warehouse) => (
                    <option key={warehouse.id} value={warehouse.id}>
                      {warehouse.name} ({warehouse.type.replace('_', ' ')})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Stock In Form */}
            {activeTab === 'stock-in' && (
              <form onSubmit={handleStockIn} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Quantity *</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={stockInData.quantity}
                      onChange={(e) => setStockInData({ ...stockInData, quantity: parseFloat(e.target.value) || 0 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Unit Cost *</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={stockInData.unit_cost}
                      onChange={(e) => setStockInData({ ...stockInData, unit_cost: parseFloat(e.target.value) || 0 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Batch Number</label>
                    <input
                      type="text"
                      value={stockInData.batch_number}
                      onChange={(e) => setStockInData({ ...stockInData, batch_number: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Supplier</label>
                    <select
                      value={selectedSupplier}
                      onChange={(e) => setSelectedSupplier(e.target.value ? Number(e.target.value) : '')}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value="">Select supplier (optional)...</option>
                      {suppliersData?.items?.map((supplier) => (
                        <option key={supplier.id} value={supplier.id}>
                          {supplier.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Quality Status</label>
                    <select
                      value={stockInData.quality_status}
                      onChange={(e) => setStockInData({ ...stockInData, quality_status: e.target.value as QualityStatus })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value="PENDING">Pending</option>
                      <option value="APPROVED">Approved</option>
                      <option value="REJECTED">Rejected</option>
                      <option value="QUARANTINE">Quarantine</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Entry Date</label>
                    <input
                      type="date"
                      value={stockInData.entry_date}
                      onChange={(e) => setStockInData({ ...stockInData, entry_date: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Expiry Date</label>
                    <input
                      type="date"
                      value={stockInData.expiry_date}
                      onChange={(e) => setStockInData({ ...stockInData, expiry_date: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Notes</label>
                  <textarea
                    value={stockInData.notes}
                    onChange={(e) => setStockInData({ ...stockInData, notes: e.target.value })}
                    rows={3}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={isSubmitting || !selectedProduct || !selectedWarehouse}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    {isSubmitting ? 'Processing...' : 'Add to Stock'}
                  </button>
                </div>
              </form>
            )}

            {/* Stock Out Form */}
            {activeTab === 'stock-out' && (
              <form onSubmit={handleStockOut} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Quantity *</label>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={stockOutData.quantity}
                      onChange={(e) => setStockOutData({ ...stockOutData, quantity: parseFloat(e.target.value) || 0 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Reference Type</label>
                    <input
                      type="text"
                      value={stockOutData.reference_type}
                      onChange={(e) => setStockOutData({ ...stockOutData, reference_type: e.target.value })}
                      placeholder="e.g., Production Order, Sale"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Reference ID</label>
                    <input
                      type="text"
                      value={stockOutData.reference_id}
                      onChange={(e) => setStockOutData({ ...stockOutData, reference_id: e.target.value })}
                      placeholder="e.g., PO-001, SO-123"
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Notes</label>
                  <textarea
                    value={stockOutData.notes}
                    onChange={(e) => setStockOutData({ ...stockOutData, notes: e.target.value })}
                    rows={3}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={isSubmitting || !selectedProduct || !selectedWarehouse}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <MinusIcon className="h-4 w-4 mr-2" />
                    {isSubmitting ? 'Processing...' : 'Remove from Stock'}
                  </button>
                </div>
              </form>
            )}

            {/* Stock Adjustment Form */}
            {activeTab === 'adjustment' && (
              <form onSubmit={handleAdjustment} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Adjustment Quantity *</label>
                    <input
                      type="number"
                      step="0.01"
                      value={adjustmentData.adjustment_quantity}
                      onChange={(e) => setAdjustmentData({ ...adjustmentData, adjustment_quantity: parseFloat(e.target.value) || 0 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="Positive for increase, negative for decrease"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">Use positive numbers to increase stock, negative to decrease</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Reason *</label>
                    <select
                      value={adjustmentData.reason}
                      onChange={(e) => setAdjustmentData({ ...adjustmentData, reason: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      required
                    >
                      <option value="">Select reason...</option>
                      <option value="Physical Count">Physical Count</option>
                      <option value="Damage">Damage</option>
                      <option value="Loss">Loss</option>
                      <option value="Found">Found</option>
                      <option value="Quality Issue">Quality Issue</option>
                      <option value="System Correction">System Correction</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Notes</label>
                  <textarea
                    value={adjustmentData.notes}
                    onChange={(e) => setAdjustmentData({ ...adjustmentData, notes: e.target.value })}
                    rows={3}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Detailed explanation for the adjustment"
                  />
                </div>

                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={isSubmitting || !selectedProduct || !selectedWarehouse}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ArrowsUpDownIcon className="h-4 w-4 mr-2" />
                    {isSubmitting ? 'Processing...' : 'Adjust Stock'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>

        {/* Stock Availability Info */}
        <div className="space-y-6">
          {selectedProduct && selectedWarehouse && stockAvailability && (
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center mb-4">
                <InformationCircleIcon className="h-5 w-5 text-blue-500 mr-2" />
                <h3 className="text-lg font-medium text-gray-900">Current Stock</h3>
              </div>
              
              <div className="space-y-3">
                <div>
                  <span className="text-sm text-gray-500">Available Quantity:</span>
                  <div className="text-lg font-semibold text-gray-900">
                    {formatNumber(stockAvailability.total_available)}
                  </div>
                </div>

                <div>
                  <span className="text-sm text-gray-500">Weighted Average Cost:</span>
                  <div className="text-lg font-semibold text-gray-900">
                    {formatCurrency(stockAvailability.weighted_average_cost)}
                  </div>
                </div>

                {stockAvailability.fifo_batches && stockAvailability.fifo_batches.length > 0 && (
                  <div>
                    <span className="text-sm text-gray-500 block mb-2">FIFO Batches:</span>
                    <div className="space-y-2">
                      {stockAvailability.fifo_batches.slice(0, 3).map((batch, index) => (
                        <div key={`batch-${batch.batch_number}-${index}`} className="bg-gray-50 p-2 rounded text-sm">
                          <div className="flex justify-between">
                            <span>Batch: {batch.batch_number}</span>
                            <span>{formatNumber(batch.available_quantity)}</span>
                          </div>
                          <div className="flex justify-between text-gray-600">
                            <span>Cost: {formatCurrency(batch.unit_cost)}</span>
                            <span>{new Date(batch.entry_date).toLocaleDateString()}</span>
                          </div>
                        </div>
                      ))}
                      {stockAvailability.fifo_batches.length > 3 && (
                        <div className="text-xs text-gray-500">
                          +{stockAvailability.fifo_batches.length - 3} more batches
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {!selectedProduct || !selectedWarehouse ? (
            <div className="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
              <InformationCircleIcon className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500">
                Select a product and warehouse to view current stock information
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}