'use client';

import { useState } from 'react';
import { useProductionOrders, useCreateProductionOrder, useUpdateProductionOrder, useDeleteProductionOrder } from '@/hooks/use-production-orders';
import { useBOMs } from '@/hooks/use-bom';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { ProductionOrder, CreateProductionOrderRequest, ProductionOrderStatus } from '@/types/api';
import { formatDate, handleAPIError, debounce } from '@/lib/utils';
import { 
  PlusIcon, 
  PencilIcon, 
  TrashIcon, 
  MagnifyingGlassIcon,
  EyeIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  PlayIcon
} from '@heroicons/react/24/outline';

type ProductionOrderFormData = CreateProductionOrderRequest;

const getStatusColor = (status: ProductionOrderStatus) => {
  switch (status) {
    case 'PENDING':
      return 'bg-yellow-100 text-yellow-800';
    case 'IN_PROGRESS':
      return 'bg-blue-100 text-blue-800';
    case 'COMPLETED':
      return 'bg-green-100 text-green-800';
    case 'CANCELLED':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

const getStatusIcon = (status: ProductionOrderStatus) => {
  switch (status) {
    case 'PENDING':
      return <ClockIcon className="h-4 w-4" />;
    case 'IN_PROGRESS':
      return <PlayIcon className="h-4 w-4" />;
    case 'COMPLETED':
      return <CheckCircleIcon className="h-4 w-4" />;
    case 'CANCELLED':
      return <XCircleIcon className="h-4 w-4" />;
    default:
      return null;
  }
};

export default function ProductionOrdersPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProductionOrderStatus | ''>('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingOrder, setEditingOrder] = useState<ProductionOrder | null>(null);
  const [viewingOrder, setViewingOrder] = useState<ProductionOrder | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const debouncedSearch = debounce((value: string) => {
    setSearchTerm(value);
    setCurrentPage(1);
  }, 300);

  const { data, isLoading, error } = useProductionOrders({
    page: currentPage,
    page_size: 20,
    search: searchTerm || undefined,
    status: statusFilter || undefined,
  });

  const { data: bomsData, isLoading: isLoadingBOMs, error: bomsError } = useBOMs({ page_size: 1000 });
  const boms = bomsData?.items || [];

  const { data: productsData } = useProducts({ page_size: 1000 });
  const products = productsData?.items || [];

  const { data: warehousesData } = useWarehouses({ page_size: 100 });
  const warehouses = warehousesData?.items || [];

  const createOrder = useCreateProductionOrder();
  const updateOrder = useUpdateProductionOrder();
  const deleteOrder = useDeleteProductionOrder();

  const [formData, setFormData] = useState<ProductionOrderFormData>({
    product_id: 0,
    bom_id: 0,
    warehouse_id: 0,
    planned_quantity: 1,
    priority: 5,
    planned_start_date: '',
    planned_completion_date: '',
    notes: '',
  });

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.product_id) errors.product_id = 'Product is required';
    if (!formData.bom_id) errors.bom_id = 'BOM is required';
    if (!formData.warehouse_id) errors.warehouse_id = 'Warehouse is required';
    if (!formData.planned_quantity || formData.planned_quantity <= 0) {
      errors.planned_quantity = 'Quantity must be greater than 0';
    }
    if (formData.priority && (formData.priority < 1 || formData.priority > 10)) {
      errors.priority = 'Priority must be between 1 and 10';
    }
    if (formData.planned_start_date && formData.planned_completion_date) {
      if (new Date(formData.planned_start_date) > new Date(formData.planned_completion_date)) {
        errors.planned_completion_date = 'End date must be after start date';
      }
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    try {
      const submitData = {
        ...formData,
        planned_start_date: formData.planned_start_date || undefined,
        planned_completion_date: formData.planned_completion_date || undefined,
        priority: formData.priority || undefined,
        notes: formData.notes || undefined,
      };

      if (editingOrder) {
        await updateOrder.mutateAsync({
          id: editingOrder.production_order_id || editingOrder.id!,
          data: submitData,
        });
      } else {
        await createOrder.mutateAsync(submitData);
      }
      handleCloseModal();
    } catch (error) {
      alert(handleAPIError(error));
    }
  };

  const handleEdit = (order: ProductionOrder) => {
    setEditingOrder(order);
    setFormData({
      product_id: order.product?.product_id || order.product?.id || 0,
      bom_id: order.bom_id,
      warehouse_id: order.warehouse?.warehouse_id || order.warehouse?.id || 0,
      planned_quantity: order.quantity_to_produce,
      priority: typeof order.priority === 'string' ? parseInt(order.priority) || 5 : (order.priority || 5),
      planned_start_date: order.planned_start_date ? order.planned_start_date.split('T')[0] : '',
      planned_completion_date: order.planned_end_date ? order.planned_end_date.split('T')[0] : '',
      notes: order.notes || '',
    });
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleView = (order: ProductionOrder) => {
    setViewingOrder(order);
  };

  const handleDelete = async (order: ProductionOrder) => {
    if (confirm(`Are you sure you want to delete production order "${order.order_number}"?`)) {
      try {
        await deleteOrder.mutateAsync(order.production_order_id || order.id!);
      } catch (error) {
        alert(handleAPIError(error));
      }
    }
  };

  const handleStatusUpdate = async (order: ProductionOrder, newStatus: ProductionOrderStatus) => {
    try {
      await updateOrder.mutateAsync({
        id: order.production_order_id || order.id!,
        data: { status: newStatus },
      });
    } catch (error) {
      alert(handleAPIError(error));
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingOrder(null);
    setFormData({
      product_id: 0,
      bom_id: 0,
      warehouse_id: 0,
      planned_quantity: 1,
      priority: 5,
      planned_start_date: '',
      planned_completion_date: '',
      notes: '',
    });
    setFormErrors({});
  };

  const getSelectedBOM = () => {
    return boms.find(bom => (bom.bom_id ?? bom.id) === formData.bom_id);
  };

  if (error) {
    return <div className="text-red-600">Error: {handleAPIError(error)}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Production Orders</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage production orders and track manufacturing progress
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
        >
          <PlusIcon className="h-4 w-4 mr-2" />
          Create Order
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow space-y-4 sm:space-y-0 sm:flex sm:items-center sm:space-x-4">
        <div className="flex-1">
          <div className="relative">
            <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search orders..."
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
              onChange={(e) => debouncedSearch(e.target.value)}
            />
          </div>
        </div>
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as ProductionOrderStatus | '');
            setCurrentPage(1);
          }}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
        >
          <option value="">All Statuses</option>
          <option value="PENDING">Pending</option>
          <option value="IN_PROGRESS">In Progress</option>
          <option value="COMPLETED">Completed</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
      </div>

      {/* Orders Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Order Number
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Product / BOM
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Quantity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Planned Dates
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center">
                    <div className="animate-pulse">Loading orders...</div>
                  </td>
                </tr>
              ) : data?.items?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-4 text-center text-gray-500">
                    No production orders found
                  </td>
                </tr>
              ) : (
                data?.items?.map((order) => (
                  <tr key={order.production_order_id || order.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-gray-900">
                        {order.order_number}
                      </div>
                      {order.priority && (
                        <div className="text-sm text-gray-500">
                          Priority: {order.priority}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {order.product?.product_name}
                        </div>
                        <div className="text-sm text-gray-500">
                          BOM: {order.bom?.bom_name} (v{order.bom?.version})
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">
                        {order.quantity_produced || 0} / {order.quantity_to_produce}
                      </div>
                      <div className="text-sm text-gray-500">
                        {order.product?.unit_of_measure}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(order.status)}`}>
                        {getStatusIcon(order.status)}
                        <span className="ml-1">{order.status.replace('_', ' ')}</span>
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {order.planned_start_date && (
                        <div>Start: {formatDate(order.planned_start_date)}</div>
                      )}
                      {order.planned_end_date && (
                        <div>End: {formatDate(order.planned_end_date)}</div>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatDate(order.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm font-medium">
                      <div className="flex justify-end space-x-2">
                        <button
                          onClick={() => handleView(order)}
                          className="text-blue-600 hover:text-blue-900"
                          title="View Details"
                        >
                          <EyeIcon className="h-4 w-4" />
                        </button>
                        
                        {/* Quick Status Updates */}
                        {order.status === 'PENDING' && (
                          <button
                            onClick={() => handleStatusUpdate(order, 'IN_PROGRESS')}
                            className="text-blue-600 hover:text-blue-900"
                            title="Start Production"
                          >
                            <PlayIcon className="h-4 w-4" />
                          </button>
                        )}
                        
                        {order.status === 'IN_PROGRESS' && (
                          <button
                            onClick={() => handleStatusUpdate(order, 'COMPLETED')}
                            className="text-green-600 hover:text-green-900"
                            title="Mark as Completed"
                          >
                            <CheckCircleIcon className="h-4 w-4" />
                          </button>
                        )}
                        
                        <button
                          onClick={() => handleEdit(order)}
                          className="text-indigo-600 hover:text-indigo-900"
                          title="Edit"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </button>
                        
                        {order.status !== 'COMPLETED' && (
                          <button
                            onClick={() => handleDelete(order)}
                            className="text-red-600 hover:text-red-900"
                            title="Delete"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="bg-white px-6 py-3 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing {((currentPage - 1) * 20) + 1} to {Math.min(currentPage * 20, data.total)} of {data.total} results
            </div>
            <div className="flex space-x-2">
              <button
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={!data.has_previous}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={!data.has_next}
                className="px-3 py-1 border border-gray-300 rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-full max-w-2xl shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                {editingOrder ? 'Edit Production Order' : 'Create New Production Order'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Product</label>
                  <select
                    value={formData.product_id || 0}
                    onChange={(e) => setFormData({ ...formData, product_id: parseInt(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value={0}>Select Product</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.code})
                      </option>
                    ))}
                  </select>
                  {formErrors.product_id && <p className="text-red-500 text-xs mt-1">{formErrors.product_id}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Warehouse</label>
                  <select
                    value={formData.warehouse_id || 0}
                    onChange={(e) => setFormData({ ...formData, warehouse_id: parseInt(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value={0}>Select Warehouse</option>
                    {warehouses.map((warehouse) => (
                      <option key={warehouse.id} value={warehouse.id}>
                        {warehouse.name} ({warehouse.type?.replace('_', ' ')})
                      </option>
                    ))}
                  </select>
                  {formErrors.warehouse_id && <p className="text-red-500 text-xs mt-1">{formErrors.warehouse_id}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">BOM</label>
                  <select
                    value={formData.bom_id || 0}
                    onChange={(e) => setFormData({ ...formData, bom_id: parseInt(e.target.value) || 0 })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    disabled={isLoadingBOMs}
                  >
                    <option value={0}>
                      {isLoadingBOMs ? 'Loading BOMs...' : bomsError ? 'Error loading BOMs' : 'Select BOM'}
                    </option>
                    {boms.map((bom) => {
                      const bomId = bom.bom_id ?? bom.id;
                      const bomName = bom.bom_name ?? bom.name ?? 'Unknown BOM';
                      return (
                        <option key={bomId} value={bomId}>
                          {bomName} - {bom.product?.product_name ?? 'Unknown Product'} (v{bom.version})
                        </option>
                      );
                    })}
                  </select>
                  {formErrors.bom_id && <p className="text-red-500 text-xs mt-1">{formErrors.bom_id}</p>}
                  
                  {/* Debug info */}
                  <p className="text-xs text-gray-500 mt-1">
                    {boms.length} BOMs available
                    {bomsError && ` (Error: ${bomsError})`}
                  </p>
                  
                  {/* BOM Info */}
                  {getSelectedBOM() && (
                    <div className="mt-2 p-3 bg-blue-50 rounded-md">
                      <p className="text-sm text-blue-900">
                        <strong>Product:</strong> {getSelectedBOM()?.product?.product_name} ({getSelectedBOM()?.product?.product_code})
                      </p>
                      <p className="text-sm text-blue-900">
                        <strong>BOM Code:</strong> {getSelectedBOM()?.bom_code || getSelectedBOM()?.code}
                      </p>
                      <p className="text-sm text-blue-900">
                        <strong>Items:</strong> {getSelectedBOM()?.bom_items?.length || 0} components
                      </p>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Planned Quantity</label>
                    <input
                      type="number"
                      min="1"
                      step="0.01"
                      value={formData.planned_quantity || 1}
                      onChange={(e) => setFormData({ ...formData, planned_quantity: parseFloat(e.target.value) || 1 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {formErrors.planned_quantity && <p className="text-red-500 text-xs mt-1">{formErrors.planned_quantity}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Priority (1-10)</label>
                    <select
                      value={formData.priority || 5}
                      onChange={(e) => setFormData({ ...formData, priority: parseInt(e.target.value) || 5 })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value={1}>1 - Highest Priority</option>
                      <option value={2}>2 - Very High</option>
                      <option value={3}>3 - High</option>
                      <option value={4}>4 - Above Normal</option>
                      <option value={5}>5 - Normal</option>
                      <option value={6}>6 - Below Normal</option>
                      <option value={7}>7 - Low</option>
                      <option value={8}>8 - Very Low</option>
                      <option value={9}>9 - Lowest</option>
                      <option value={10}>10 - Lowest Priority</option>
                    </select>
                    {formErrors.priority && <p className="text-red-500 text-xs mt-1">{formErrors.priority}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Planned Start Date</label>
                    <input
                      type="date"
                      value={formData.planned_start_date || ''}
                      onChange={(e) => setFormData({ ...formData, planned_start_date: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Planned Completion Date</label>
                    <input
                      type="date"
                      value={formData.planned_completion_date || ''}
                      onChange={(e) => setFormData({ ...formData, planned_completion_date: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {formErrors.planned_completion_date && <p className="text-red-500 text-xs mt-1">{formErrors.planned_completion_date}</p>}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Notes</label>
                  <textarea
                    value={formData.notes || ''}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                <div className="flex justify-end space-x-3 pt-4">
                  <button
                    type="button"
                    onClick={handleCloseModal}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createOrder.isPending || updateOrder.isPending}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {createOrder.isPending || updateOrder.isPending
                      ? 'Saving...'
                      : editingOrder
                      ? 'Update'
                      : 'Create'
                    }
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* View Modal */}
      {viewingOrder && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Production Order Details: {viewingOrder.order_number}
              </h3>
              
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div>
                      <p className="text-sm font-medium text-gray-700">Order Number</p>
                      <p className="text-sm text-gray-900">{viewingOrder.order_number}</p>
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">Status</p>
                      <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(viewingOrder.status)}`}>
                        {getStatusIcon(viewingOrder.status)}
                        <span className="ml-1">{viewingOrder.status.replace('_', ' ')}</span>
                      </span>
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">Product</p>
                      <p className="text-sm text-gray-900">
                        {viewingOrder.product?.product_name} ({viewingOrder.product?.product_code})
                      </p>
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">BOM</p>
                      <p className="text-sm text-gray-900">
                        {viewingOrder.bom?.bom_name} (v{viewingOrder.bom?.version})
                      </p>
                      <p className="text-sm text-gray-500">
                        Code: {viewingOrder.bom?.bom_code}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">Quantity</p>
                      <p className="text-sm text-gray-900">
                        {viewingOrder.quantity_produced || 0} / {viewingOrder.quantity_to_produce} {viewingOrder.product?.unit_of_measure}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    {viewingOrder.priority && (
                      <div>
                        <p className="text-sm font-medium text-gray-700">Priority</p>
                        <p className="text-sm text-gray-900">{viewingOrder.priority}</p>
                      </div>
                    )}

                    <div>
                      <p className="text-sm font-medium text-gray-700">Planned Dates</p>
                      {viewingOrder.planned_start_date && (
                        <p className="text-sm text-gray-900">Start: {formatDate(viewingOrder.planned_start_date)}</p>
                      )}
                      {viewingOrder.planned_end_date && (
                        <p className="text-sm text-gray-900">End: {formatDate(viewingOrder.planned_end_date)}</p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">Actual Dates</p>
                      {viewingOrder.actual_start_date && (
                        <p className="text-sm text-gray-900">Started: {formatDate(viewingOrder.actual_start_date)}</p>
                      )}
                      {viewingOrder.actual_end_date && (
                        <p className="text-sm text-gray-900">Completed: {formatDate(viewingOrder.actual_end_date)}</p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm font-medium text-gray-700">Created</p>
                      <p className="text-sm text-gray-900">{formatDate(viewingOrder.created_at)}</p>
                      {viewingOrder.created_by_user && (
                        <p className="text-sm text-gray-500">by {viewingOrder.created_by_user.full_name}</p>
                      )}
                    </div>
                  </div>
                </div>

                {viewingOrder.notes && (
                  <div>
                    <p className="text-sm font-medium text-gray-700">Notes</p>
                    <p className="text-sm text-gray-900">{viewingOrder.notes}</p>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-6">
                <button
                  onClick={() => setViewingOrder(null)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}