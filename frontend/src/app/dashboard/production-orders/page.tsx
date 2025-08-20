'use client';

import { useState, useEffect } from 'react';
import { useProductionOrders, useCreateProductionOrder, useCreateProductionOrderWithAnalysis, useUpdateProductionOrder, useDeleteProductionOrder, useEnhancedProductionOrder, useProductionOrderComponents, useUpdateComponentStatus, useProductionOrderReservations, useAnalyzeStockAvailability } from '@/hooks/use-production-orders';
import { useBOMs } from '@/hooks/use-bom';
import { useProducts } from '@/hooks/use-products';
import { useWarehouses } from '@/hooks/use-warehouses';
import { ProductionOrder, CreateProductionOrderRequest, ProductionOrderStatus, ProductionOrderStockAnalysis, ComponentStatus, EnhancedProductionOrder, ProductionOrderComponent } from '@/types/api';
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
  PlayIcon,
  ChartBarIcon,
  ExclamationTriangleIcon,
  CogIcon,
  ArrowPathIcon
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

const getComponentStatusColor = (status: ComponentStatus) => {
  switch (status) {
    case 'PENDING':
      return 'bg-yellow-100 text-yellow-800';
    case 'ALLOCATED':
      return 'bg-blue-100 text-blue-800';
    case 'CONSUMED':
      return 'bg-purple-100 text-purple-800';
    case 'COMPLETED':
      return 'bg-green-100 text-green-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
};

const getComponentStatusIcon = (status: ComponentStatus) => {
  switch (status) {
    case 'PENDING':
      return <ClockIcon className="h-4 w-4" />;
    case 'ALLOCATED':
      return <CogIcon className="h-4 w-4" />;
    case 'CONSUMED':
      return <ArrowPathIcon className="h-4 w-4" />;
    case 'COMPLETED':
      return <CheckCircleIcon className="h-4 w-4" />;
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
  const [stockAnalysis, setStockAnalysis] = useState<ProductionOrderStockAnalysis | null>(null);
  const [showStockAnalysis, setShowStockAnalysis] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [showAdvancedOptions, setShowAdvancedOptions] = useState(false);
  const [autoCreateMissing, setAutoCreateMissing] = useState(false);
  const [showComponents, setShowComponents] = useState(false);
  const [showReservations, setShowReservations] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

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
  const createOrderWithAnalysis = useCreateProductionOrderWithAnalysis();
  const updateOrder = useUpdateProductionOrder();
  const deleteOrder = useDeleteProductionOrder();
  const updateComponentStatus = useUpdateComponentStatus();
  const analyzeStock = useAnalyzeStockAvailability();

  // Enhanced production order data for viewing
  const { data: enhancedOrder } = useEnhancedProductionOrder(
    viewingOrder ? (viewingOrder.production_order_id || viewingOrder.id!) : 0
  );
  const { data: orderComponents } = useProductionOrderComponents(
    viewingOrder ? (viewingOrder.production_order_id || viewingOrder.id!) : 0
  );
  const { data: stockReservations } = useProductionOrderReservations(
    viewingOrder ? (viewingOrder.production_order_id || viewingOrder.id!) : 0
  );

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
        // Use advanced creation if analysis was done or auto-create is enabled
        if (stockAnalysis || autoCreateMissing) {
          const advancedData = {
            ...submitData,
            auto_create_missing: autoCreateMissing,
          };
          const result = await createOrderWithAnalysis.mutateAsync(advancedData);
          
          // Show result information
          if (result.nested_orders_created && result.nested_orders_created.length > 0) {
            alert(`Production order created successfully! ${result.nested_orders_created.length} additional orders were created for missing semi-finished products.`);
          }
          
          if (result.warnings && result.warnings.length > 0) {
            alert('Warnings:\n' + result.warnings.join('\n'));
          }
        } else {
          // Use simple creation
          await createOrder.mutateAsync(submitData);
        }
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

  const handleComponentStatusUpdate = async (component: ProductionOrderComponent, newStatus: ComponentStatus) => {
    const orderId = viewingOrder?.production_order_id || viewingOrder?.id!;
    try {
      await updateComponentStatus.mutateAsync({
        productionOrderId: orderId,
        data: {
          component_id: component.component_id,
          status: newStatus,
          consumed_quantity: newStatus === 'CONSUMED' ? component.required_quantity : component.consumed_quantity,
        },
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
    setStockAnalysis(null);
    setShowStockAnalysis(false);
    setAnalysisError(null);
    setIsAnalyzing(false);
  };

  // Stock analysis functionality
  const canAnalyzeStock = () => {
    return formData.bom_id && formData.warehouse_id && formData.planned_quantity > 0;
  };

  const handleStockAnalysis = async () => {
    if (!canAnalyzeStock()) {
      alert('Please select BOM, warehouse, and quantity before analyzing stock.');
      return;
    }

    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      // Create a temporary analysis request
      const analysisRequest = {
        bom_id: formData.bom_id,
        warehouse_id: formData.warehouse_id,
        quantity_to_produce: formData.planned_quantity,
      };

      const analysis = await analyzeStock.mutateAsync(analysisRequest);
      setStockAnalysis(analysis);
      setShowStockAnalysis(true);
      setAnalysisError(null);
    } catch (error) {
      const errorMessage = handleAPIError(error);
      setAnalysisError(errorMessage);
      alert(errorMessage);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Automatic stock analysis when all required fields are filled
  const performAutoStockAnalysis = async () => {
    if (!canAnalyzeStock() || isAnalyzing) return;

    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const analysisRequest = {
        bom_id: formData.bom_id,
        warehouse_id: formData.warehouse_id,
        quantity_to_produce: formData.planned_quantity,
      };

      const analysis = await analyzeStock.mutateAsync(analysisRequest);
      setStockAnalysis(analysis);
      setShowStockAnalysis(true);
      setAnalysisError(null);
    } catch (error) {
      // For auto-analysis, just set the error state without alerting
      setAnalysisError('Auto-analysis failed: Network error');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getSelectedBOM = () => {
    return boms.find(bom => (bom.bom_id ?? bom.id) === formData.bom_id);
  };

  // Filter BOMs based on selected product
  const getFilteredBOMs = () => {
    if (!formData.product_id) {
      return boms; // Show all BOMs if no product is selected
    }
    return boms.filter(bom => {
      const bomProductId = bom.product?.product_id || bom.product_id;
      return bomProductId === formData.product_id;
    });
  };

  // Handle product selection and clear BOM if it doesn't match
  const handleProductChange = (productId: number) => {
    // Check if current BOM is still valid for the new product
    const currentBOM = getSelectedBOM();
    const isCurrentBOMValid = currentBOM && (currentBOM.product?.product_id || currentBOM.product_id) === productId;
    
    setFormData({
      ...formData,
      product_id: productId,
      bom_id: isCurrentBOMValid ? formData.bom_id : 0, // Clear BOM if it doesn't match the product
    });
  };

  // Handle BOM selection and automatic product assignment
  const handleBOMChange = (bomId: number) => {
    const selectedBOM = boms.find(bom => (bom.bom_id ?? bom.id) === bomId);
    if (selectedBOM && selectedBOM.product) {
      setFormData({
        ...formData,
        bom_id: bomId,
        product_id: selectedBOM.product.product_id || selectedBOM.product_id,
      });
    } else {
      setFormData({
        ...formData,
        bom_id: bomId,
      });
    }
  };

  // Automatic stock analysis when required fields change
  useEffect(() => {
    if (!editingOrder && canAnalyzeStock()) {
      const delayedAnalysis = setTimeout(() => {
        performAutoStockAnalysis();
      }, 500); // Debounce for 500ms to avoid too many API calls

      return () => clearTimeout(delayedAnalysis);
    }
  }, [formData.bom_id, formData.warehouse_id, formData.planned_quantity]);

  // Clear analysis when form is reset or key fields are cleared
  useEffect(() => {
    if (!formData.bom_id || !formData.warehouse_id || formData.planned_quantity <= 0) {
      setStockAnalysis(null);
      setShowStockAnalysis(false);
    }
  }, [formData.bom_id, formData.warehouse_id, formData.planned_quantity]);

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
                    onChange={(e) => handleProductChange(parseInt(e.target.value) || 0)}
                    disabled={!productsData || products.length === 0}
                    className={`mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 ${
                      !productsData || products.length === 0 ? 'bg-gray-100 cursor-not-allowed' : ''
                    }`}
                  >
                    <option value={0}>
                      {!productsData ? 'Loading products...' : products.length === 0 ? 'No products available' : 'Select Product'}
                    </option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.code})
                      </option>
                    ))}
                  </select>
                  {formErrors.product_id && <p className="text-red-500 text-xs mt-1">{formErrors.product_id}</p>}
                  {!!formData.product_id && (
                    <p className="text-blue-600 text-xs mt-1">
                      {getFilteredBOMs().length} BOM{getFilteredBOMs().length !== 1 ? 's' : ''} available for this product
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Warehouse</label>
                  <select
                    value={formData.warehouse_id || 0}
                    onChange={(e) => setFormData({ ...formData, warehouse_id: parseInt(e.target.value) || 0 })}
                    disabled={!warehousesData || warehouses.length === 0}
                    className={`mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 ${
                      !warehousesData || warehouses.length === 0 ? 'bg-gray-100 cursor-not-allowed' : ''
                    }`}
                  >
                    <option value={0}>
                      {!warehousesData ? 'Loading warehouses...' : warehouses.length === 0 ? 'No warehouses available' : 'Select Warehouse'}
                    </option>
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
                  <div className="flex space-x-2">
                    <select
                      value={formData.bom_id || 0}
                      onChange={(e) => handleBOMChange(parseInt(e.target.value) || 0)}
                      className="flex-1 mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                      disabled={isLoadingBOMs}
                    >
                      <option value={0}>
                        {isLoadingBOMs ? 'Loading BOMs...' : bomsError ? 'Error loading BOMs' : 'Select BOM'}
                      </option>
                      {getFilteredBOMs().map((bom) => {
                        const bomId = bom.bom_id ?? bom.id;
                        const bomName = bom.bom_name ?? bom.name ?? 'Unknown BOM';
                        return (
                          <option key={bomId} value={bomId}>
                            {bomName} - {bom.product?.product_name ?? 'Unknown Product'} (v{bom.version})
                          </option>
                        );
                      })}
                    </select>
                    {formData.bom_id && (
                      <button
                        type="button"
                        onClick={() => setFormData({ ...formData, bom_id: 0, product_id: 0 })}
                        className="mt-1 px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
                        title="Clear BOM selection"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                  {formErrors.bom_id && <p className="text-red-500 text-xs mt-1">{formErrors.bom_id}</p>}
                  
                  {/* Debug info */}
                  <p className="text-xs text-gray-500 mt-1">
                    {getFilteredBOMs().length} BOMs available {formData.product_id ? 'for selected product' : 'total'}
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

                {/* Stock Analysis Section */}
                {!editingOrder && (
                  <div className="border-t pt-4">
                    <div className="flex justify-between items-center mb-4">
                      <h4 className="text-md font-medium text-gray-700">
                        Stock Analysis
                        {isAnalyzing && (
                          <span className="ml-2 text-sm text-blue-600">
                            <ArrowPathIcon className="h-4 w-4 inline animate-spin mr-1" />
                            Analyzing...
                          </span>
                        )}
                      </h4>
                      <button
                        type="button"
                        onClick={handleStockAnalysis}
                        disabled={!canAnalyzeStock() || isAnalyzing}
                        className={`inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md ${
                          canAnalyzeStock() && !isAnalyzing
                            ? 'text-white bg-blue-600 hover:bg-blue-700'
                            : 'text-gray-400 bg-gray-200 cursor-not-allowed'
                        }`}
                      >
                        <ChartBarIcon className="h-4 w-4 mr-2" />
                        {isAnalyzing ? 'Analyzing...' : 'Manual Check'}
                      </button>
                    </div>

                    {/* Auto-analysis info */}
                    {canAnalyzeStock() && !showStockAnalysis && !isAnalyzing && !analysisError && (
                      <div className="mb-4 p-3 bg-blue-50 rounded-md">
                        <p className="text-sm text-blue-800">
                          Stock analysis will run automatically when you complete the form.
                        </p>
                      </div>
                    )}

                    {/* Analysis error display */}
                    {analysisError && (
                      <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                        <div className="flex items-center">
                          <ExclamationTriangleIcon className="h-4 w-4 text-red-600 mr-2" />
                          <p className="text-sm text-red-800">{analysisError}</p>
                          <button
                            type="button"
                            onClick={() => setAnalysisError(null)}
                            className="ml-auto text-red-600 hover:text-red-800"
                          >
                            <XCircleIcon className="h-4 w-4" />
                          </button>
                        </div>
                        {canAnalyzeStock() && (
                          <button
                            type="button"
                            onClick={handleStockAnalysis}
                            className="mt-2 text-sm text-red-700 hover:text-red-900 underline"
                          >
                            Try manual analysis
                          </button>
                        )}
                      </div>
                    )}

                    {showStockAnalysis && stockAnalysis && (
                      <div className="space-y-4">
                        {/* Analysis Summary */}
                        <div className={`p-4 rounded-md ${
                          stockAnalysis.can_produce ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
                        }`}>
                          <div className="flex items-center">
                            {stockAnalysis.can_produce ? (
                              <CheckCircleIcon className="h-5 w-5 text-green-600 mr-2" />
                            ) : (
                              <ExclamationTriangleIcon className="h-5 w-5 text-red-600 mr-2" />
                            )}
                            <div>
                              <h5 className={`font-medium ${
                                stockAnalysis.can_produce ? 'text-green-800' : 'text-red-800'
                              }`}>
                                {stockAnalysis.can_produce ? 'Stock Available' : 'Insufficient Stock'}
                              </h5>
                              <p className={`text-sm ${
                                stockAnalysis.can_produce ? 'text-green-700' : 'text-red-700'
                              }`}>
                                {stockAnalysis.can_produce 
                                  ? `Can produce ${stockAnalysis.quantity_to_produce} units`
                                  : `Missing ${stockAnalysis.missing_materials.length} materials`}
                              </p>
                            </div>
                          </div>
                        </div>

                        {/* Missing Materials */}
                        {stockAnalysis.missing_materials.length > 0 && (
                          <div>
                            <h6 className="font-medium text-gray-700 mb-2">Missing Materials</h6>
                            <div className="space-y-2">
                              {stockAnalysis.missing_materials.map((item, index) => (
                                <div key={index} className="flex justify-between items-center p-2 bg-red-50 rounded border border-red-200">
                                  <div>
                                    <span className="font-medium text-red-800">{item.product_name}</span>
                                    <span className="text-sm text-red-600 ml-2">({item.product_code})</span>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-sm text-red-700">
                                      Need: {item.required_quantity} | Available: {item.available_quantity}
                                    </div>
                                    <div className="text-sm font-medium text-red-800">
                                      Short: {item.shortage_quantity || (item.required_quantity - item.available_quantity)}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* All Materials */}
                        <div>
                          <h6 className="font-medium text-gray-700 mb-2">Material Requirements</h6>
                          <div className="space-y-2 max-h-40 overflow-y-auto">
                            {stockAnalysis.analysis_items.map((item, index) => (
                              <div key={index} className={`flex justify-between items-center p-2 rounded border ${
                                item.sufficient_stock 
                                  ? 'bg-green-50 border-green-200' 
                                  : 'bg-yellow-50 border-yellow-200'
                              }`}>
                                <div>
                                  <span className={`font-medium ${
                                    item.sufficient_stock ? 'text-green-800' : 'text-yellow-800'
                                  }`}>
                                    {item.product_name}
                                  </span>
                                  <span className={`text-sm ml-2 ${
                                    item.sufficient_stock ? 'text-green-600' : 'text-yellow-600'
                                  }`}>
                                    ({item.product_code})
                                  </span>
                                </div>
                                <div className="text-right">
                                  <div className={`text-sm ${
                                    item.sufficient_stock ? 'text-green-700' : 'text-yellow-700'
                                  }`}>
                                    Need: {item.required_quantity} | Available: {item.available_quantity}
                                  </div>
                                  {item.unit_cost && (
                                    <div className={`text-xs ${
                                      item.sufficient_stock ? 'text-green-600' : 'text-yellow-600'
                                    }`}>
                                      Cost: ${(item.total_cost || 0).toFixed(2)}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Total Cost */}
                        <div className="border-t pt-2">
                          <div className="flex justify-between text-sm">
                            <span className="font-medium text-gray-700">Estimated Material Cost:</span>
                            <span className="font-medium text-gray-900">${stockAnalysis.total_material_cost.toFixed(2)}</span>
                          </div>
                        </div>

                        {/* Advanced Options */}
                        {stockAnalysis.missing_materials.length > 0 && (
                          <div className="border-t pt-4">
                            <div className="flex items-center justify-between">
                              <h6 className="font-medium text-gray-700">Advanced Options</h6>
                              <button
                                type="button"
                                onClick={() => setShowAdvancedOptions(!showAdvancedOptions)}
                                className="text-sm text-blue-600 hover:text-blue-800"
                              >
                                {showAdvancedOptions ? 'Hide Options' : 'Show Options'}
                              </button>
                            </div>
                            
                            {showAdvancedOptions && (
                              <div className="mt-3 space-y-3">
                                <div className="flex items-start">
                                  <input
                                    type="checkbox"
                                    id="auto-create-missing"
                                    checked={autoCreateMissing}
                                    onChange={(e) => setAutoCreateMissing(e.target.checked)}
                                    className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                  />
                                  <label htmlFor="auto-create-missing" className="ml-2 text-sm text-gray-700">
                                    <span className="font-medium">Auto-create production orders for missing semi-finished products</span>
                                    <p className="text-xs text-gray-500 mt-1">
                                      This will automatically create nested production orders for any missing semi-finished products that have BOMs.
                                    </p>
                                  </label>
                                </div>

                                {autoCreateMissing && (
                                  <div className="ml-6 p-3 bg-blue-50 rounded-md">
                                    <p className="text-xs text-blue-700">
                                      <strong>Note:</strong> This will create a production tree where dependent orders are created first, 
                                      followed by the main production order once materials are available.
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

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
                    disabled={createOrder.isPending || createOrderWithAnalysis.isPending || updateOrder.isPending}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {createOrder.isPending || createOrderWithAnalysis.isPending || updateOrder.isPending
                      ? 'Saving...'
                      : editingOrder
                      ? 'Update'
                      : autoCreateMissing
                      ? 'Create with Dependencies'
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

                {/* Progress and Components Section */}
                <div className="border-t pt-6">
                  <div className="flex justify-between items-center mb-4">
                    <h4 className="text-md font-medium text-gray-700">Production Details</h4>
                    <div className="flex space-x-2">
                      <button
                        onClick={() => setShowComponents(!showComponents)}
                        className="text-sm text-blue-600 hover:text-blue-800"
                      >
                        {showComponents ? 'Hide Components' : 'Show Components'}
                      </button>
                      <button
                        onClick={() => setShowReservations(!showReservations)}
                        className="text-sm text-green-600 hover:text-green-800"
                      >
                        {showReservations ? 'Hide Reservations' : 'Show Reservations'}
                      </button>
                    </div>
                  </div>

                  {/* Overall Progress Bar */}
                  {enhancedOrder?.completion_percentage !== undefined && (
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>Overall Progress</span>
                        <span>{Math.round(enhancedOrder.completion_percentage)}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all"
                          style={{ width: `${enhancedOrder.completion_percentage}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Component Details */}
                  {showComponents && orderComponents && (
                    <div className="space-y-3">
                      <h5 className="text-sm font-medium text-gray-700">Components ({orderComponents.length})</h5>
                      <div className="space-y-2 max-h-60 overflow-y-auto">
                        {orderComponents.map((component) => (
                          <div key={component.component_id} className="border rounded-lg p-3">
                            <div className="flex justify-between items-start">
                              <div className="flex-1">
                                <div className="flex items-center space-x-2">
                                  <span className="font-medium text-gray-900">{component.product_name}</span>
                                  <span className="text-sm text-gray-500">({component.product_code})</span>
                                  <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${getComponentStatusColor(component.status)}`}>
                                    {getComponentStatusIcon(component.status)}
                                    <span className="ml-1">{component.status.replace('_', ' ')}</span>
                                  </span>
                                </div>
                                <div className="flex items-center space-x-4 text-sm text-gray-600 mt-1">
                                  <span>Required: {component.required_quantity}</span>
                                  <span>Allocated: {component.allocated_quantity}</span>
                                  <span>Consumed: {component.consumed_quantity}</span>
                                  {component.unit_cost && (
                                    <span>Cost: ${(component.total_cost || 0).toFixed(2)}</span>
                                  )}
                                </div>
                                {component.notes && (
                                  <p className="text-xs text-gray-500 mt-1">{component.notes}</p>
                                )}
                              </div>
                              
                              {/* Component Action Buttons */}
                              {viewingOrder.status === 'IN_PROGRESS' && (
                                <div className="flex space-x-1 ml-2">
                                  {component.status === 'PENDING' && (
                                    <button
                                      onClick={() => handleComponentStatusUpdate(component, 'ALLOCATED')}
                                      className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded hover:bg-blue-200"
                                      title="Allocate"
                                    >
                                      Allocate
                                    </button>
                                  )}
                                  {component.status === 'ALLOCATED' && (
                                    <button
                                      onClick={() => handleComponentStatusUpdate(component, 'CONSUMED')}
                                      className="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded hover:bg-purple-200"
                                      title="Mark as Consumed"
                                    >
                                      Consume
                                    </button>
                                  )}
                                  {component.status === 'CONSUMED' && (
                                    <button
                                      onClick={() => handleComponentStatusUpdate(component, 'COMPLETED')}
                                      className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded hover:bg-green-200"
                                      title="Mark as Completed"
                                    >
                                      Complete
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>

                            {/* Component Progress Bar */}
                            {component.required_quantity > 0 && (
                              <div className="mt-2">
                                <div className="w-full bg-gray-200 rounded-full h-1">
                                  <div
                                    className="bg-green-600 h-1 rounded-full transition-all"
                                    style={{ 
                                      width: `${Math.min(100, (component.consumed_quantity / component.required_quantity) * 100)}%` 
                                    }}
                                  />
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Stock Reservations */}
                  {showReservations && stockReservations && (
                    <div className="space-y-3 mt-6">
                      <h5 className="text-sm font-medium text-gray-700">Stock Reservations ({stockReservations.length})</h5>
                      {stockReservations.length === 0 ? (
                        <p className="text-sm text-gray-500">No stock reservations found</p>
                      ) : (
                        <div className="space-y-2 max-h-60 overflow-y-auto">
                          {stockReservations.map((reservation) => {
                            const getReservationStatusColor = (status: string) => {
                              switch (status) {
                                case 'ACTIVE':
                                  return 'bg-green-100 text-green-800';
                                case 'CONSUMED':
                                  return 'bg-blue-100 text-blue-800';
                                case 'RELEASED':
                                  return 'bg-gray-100 text-gray-800';
                                default:
                                  return 'bg-gray-100 text-gray-800';
                              }
                            };

                            return (
                              <div key={reservation.reservation_id} className="border rounded-lg p-3 bg-gray-50">
                                <div className="flex justify-between items-start">
                                  <div className="flex-1">
                                    <div className="flex items-center space-x-2">
                                      <span className="font-medium text-gray-900">{reservation.product_name}</span>
                                      <span className="text-sm text-gray-500">({reservation.product_code})</span>
                                      <span className={`inline-flex items-center px-2 py-1 text-xs font-semibold rounded-full ${getReservationStatusColor(reservation.status)}`}>
                                        {reservation.status}
                                      </span>
                                    </div>
                                    <div className="flex items-center space-x-4 text-sm text-gray-600 mt-1">
                                      <span>Quantity: {reservation.reserved_quantity}</span>
                                      <span>Warehouse: {reservation.warehouse_name}</span>
                                      {reservation.batch_number && (
                                        <span>Batch: {reservation.batch_number}</span>
                                      )}
                                      {reservation.unit_cost && (
                                        <span>Cost: ${(reservation.reserved_quantity * reservation.unit_cost).toFixed(2)}</span>
                                      )}
                                    </div>
                                    <div className="text-xs text-gray-500 mt-1">
                                      <span>Reserved: {formatDate(reservation.reservation_date)}</span>
                                      {reservation.expiry_date && (
                                        <span className="ml-3">Expires: {formatDate(reservation.expiry_date)}</span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="flex justify-end pt-6">
                <button
                  onClick={() => {
                    setViewingOrder(null);
                    setShowComponents(false);
                    setShowReservations(false);
                  }}
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