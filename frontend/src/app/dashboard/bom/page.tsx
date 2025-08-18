'use client';

import { useState } from 'react';
import { useBOMs, useCreateBOM, useUpdateBOM, useDeleteBOM, useBOMCostCalculation } from '@/hooks/use-bom';
import { useProducts } from '@/hooks/use-products';
import { BOM, CreateBOMRequest, Product } from '@/types/api';
import { formatDate, handleAPIError, debounce } from '@/lib/utils';
import { 
  PlusIcon, 
  PencilIcon, 
  TrashIcon, 
  MagnifyingGlassIcon,
  EyeIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';

type BOMFormData = Omit<CreateBOMRequest, 'bom_items'> & {
  bom_items: Array<{
    id?: string;
    product_id: number;
    quantity: number;
    notes?: string;
    product?: Product;
  }>;
};

export default function BOMPage() {
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBOM, setEditingBOM] = useState<BOM | null>(null);
  const [viewingBOM, setViewingBOM] = useState<BOM | null>(null);
  const [showCostModal, setShowCostModal] = useState(false);
  const [costCalculationId, setCostCalculationId] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const debouncedSearch = debounce((value: string) => {
    setSearchTerm(value);
    setCurrentPage(1);
  }, 300);

  const { data, isLoading, error } = useBOMs({
    page: currentPage,
    page_size: 20,
    search: searchTerm || undefined,
  });

  const { data: productsData } = useProducts({ page_size: 1000 });
  const products = productsData?.items || [];

  const { data: costCalculation } = useBOMCostCalculation(costCalculationId || 0);

  const createBOM = useCreateBOM();
  const updateBOM = useUpdateBOM();
  const deleteBOM = useDeleteBOM();

  const [formData, setFormData] = useState<BOMFormData>({
    product_id: 0,
    bom_code: '',
    bom_name: '',
    description: '',
    version: '1.0',
    bom_items: [],
  });

  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.product_id) errors.product_id = 'Product is required';
    if (!formData.bom_code.trim()) errors.bom_code = 'BOM code is required';
    if (!formData.bom_name.trim()) errors.bom_name = 'BOM name is required';
    if (!formData.version.trim()) errors.version = 'Version is required';
    if (formData.bom_items.length === 0) errors.bom_items = 'At least one BOM item is required';

    formData.bom_items.forEach((item, index) => {
      if (!item.product_id) errors[`item_${index}_product`] = 'Product is required';
      if (!item.quantity || item.quantity <= 0) errors[`item_${index}_quantity`] = 'Quantity must be greater than 0';
    });

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    try {
      const submitData: CreateBOMRequest = {
        ...formData,
        bom_items: formData.bom_items.map(item => ({
          product_id: item.product_id,
          quantity: item.quantity,
          notes: item.notes,
        })),
      };

      if (editingBOM) {
        await updateBOM.mutateAsync({
          id: editingBOM.bom_id || editingBOM.id!,
          data: submitData,
        });
      } else {
        await createBOM.mutateAsync(submitData);
      }
      handleCloseModal();
    } catch (error) {
      alert(handleAPIError(error));
    }
  };

  const handleEdit = (bom: BOM) => {
    setEditingBOM(bom);
    setFormData({
      product_id: bom.product_id,
      bom_code: bom.bom_code || bom.code || '',
      bom_name: bom.bom_name || bom.name || '',
      description: bom.description || '',
      version: bom.version,
      bom_items: bom.bom_items?.map((item, index) => ({
        id: `${item.product_id}-${index}-${Date.now()}`,
        product_id: item.product_id,
        quantity: item.quantity,
        notes: item.notes,
        product: item.product,
      })) || [],
    });
    setFormErrors({});
    setIsModalOpen(true);
  };

  const handleView = (bom: BOM) => {
    setViewingBOM(bom);
  };

  const handleViewCost = (bomId: number) => {
    setCostCalculationId(bomId);
    setShowCostModal(true);
  };

  const handleDelete = async (bom: BOM) => {
    if (confirm(`Are you sure you want to delete BOM "${bom.bom_name || bom.name}"?`)) {
      try {
        await deleteBOM.mutateAsync(bom.bom_id || bom.id!);
      } catch (error) {
        alert(handleAPIError(error));
      }
    }
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingBOM(null);
    setFormData({
      product_id: 0,
      bom_code: '',
      bom_name: '',
      description: '',
      version: '1.0',
      bom_items: [],
    });
    setFormErrors({});
  };

  const addBOMItem = () => {
    const newItem = { 
      id: `new-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      product_id: 0, 
      quantity: 1, 
      notes: '' 
    };
    setFormData({
      ...formData,
      bom_items: [...formData.bom_items, newItem],
    });
  };

  const removeBOMItem = (index: number) => {
    setFormData({
      ...formData,
      bom_items: formData.bom_items.filter((_, i) => i !== index),
    });
  };

  const updateBOMItem = (index: number, field: string, value: string | number) => {
    const newItems = [...formData.bom_items];
    newItems[index] = { ...newItems[index], [field]: value };
    
    // If product_id changes, update the product info
    if (field === 'product_id') {
      const product = products.find(p => p.product_id === value);
      newItems[index].product = product;
    }
    
    setFormData({ ...formData, bom_items: newItems });
  };

  if (error) {
    return <div className="text-red-600">Error: {handleAPIError(error)}</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Bill of Materials (BOM)</h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage your product BOMs and component requirements
          </p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
        >
          <PlusIcon className="h-4 w-4 mr-2" />
          Add BOM
        </button>
      </div>

      {/* Search */}
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="relative">
          <MagnifyingGlassIcon className="h-5 w-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search BOMs..."
            className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
            onChange={(e) => debouncedSearch(e.target.value)}
          />
        </div>
      </div>

      {/* BOMs Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  BOM
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Product
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Version
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Items Count
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
                  <td colSpan={6} className="px-6 py-4 text-center">
                    <div className="animate-pulse">Loading BOMs...</div>
                  </td>
                </tr>
              ) : data?.items?.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-4 text-center text-gray-500">
                    No BOMs found
                  </td>
                </tr>
              ) : (
                data?.items?.map((bom) => (
                  <tr key={bom.bom_id || bom.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {bom.bom_name || bom.name}
                        </div>
                        <div className="text-sm text-gray-500">
                          Code: {bom.bom_code || bom.code}
                        </div>
                        {bom.description && (
                          <div className="text-sm text-gray-400 truncate max-w-xs">
                            {bom.description}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">
                        {bom.product?.product_name}
                      </div>
                      <div className="text-sm text-gray-500">
                        {bom.product?.product_code}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {bom.version}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {bom.bom_items?.length || 0} items
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatDate(bom.created_at)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm font-medium space-x-2">
                      <button
                        onClick={() => handleView(bom)}
                        className="text-blue-600 hover:text-blue-900"
                        title="View Details"
                      >
                        <EyeIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleViewCost(bom.bom_id || bom.id!)}
                        className="text-green-600 hover:text-green-900"
                        title="View Cost Calculation"
                      >
                        <CurrencyDollarIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleEdit(bom)}
                        className="text-indigo-600 hover:text-indigo-900"
                        title="Edit"
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(bom)}
                        className="text-red-600 hover:text-red-900"
                        title="Delete"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
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
          <div className="relative top-10 mx-auto p-5 border w-full max-w-4xl shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                {editingBOM ? 'Edit BOM' : 'Add New BOM'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Product</label>
                    <select
                      value={formData.product_id}
                      onChange={(e) => setFormData({ ...formData, product_id: parseInt(e.target.value) })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      <option value={0}>Select Product</option>
                      {products.map((product) => (
                        <option key={product.product_id} value={product.product_id}>
                          {product.product_name || product.name} ({product.product_code || product.code})
                        </option>
                      ))}
                    </select>
                    {formErrors.product_id && <p className="text-red-500 text-xs mt-1">{formErrors.product_id}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">BOM Code</label>
                    <input
                      type="text"
                      value={formData.bom_code}
                      onChange={(e) => setFormData({ ...formData, bom_code: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {formErrors.bom_code && <p className="text-red-500 text-xs mt-1">{formErrors.bom_code}</p>}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">BOM Name</label>
                    <input
                      type="text"
                      value={formData.bom_name}
                      onChange={(e) => setFormData({ ...formData, bom_name: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {formErrors.bom_name && <p className="text-red-500 text-xs mt-1">{formErrors.bom_name}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Version</label>
                    <input
                      type="text"
                      value={formData.version}
                      onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                      className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                    />
                    {formErrors.version && <p className="text-red-500 text-xs mt-1">{formErrors.version}</p>}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    rows={3}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                  />
                </div>

                {/* BOM Items */}
                <div>
                  <div className="flex justify-between items-center mb-4">
                    <label className="block text-sm font-medium text-gray-700">BOM Items</label>
                    <button
                      type="button"
                      onClick={addBOMItem}
                      className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-indigo-600 bg-indigo-100 hover:bg-indigo-200"
                    >
                      <PlusIcon className="h-4 w-4 mr-1" />
                      Add Item
                    </button>
                  </div>

                  {formData.bom_items.map((item, index) => (
                    <div key={item.id || `item-${index}`} className="bg-gray-50 p-4 rounded-md mb-4">
                      <div className="grid grid-cols-4 gap-4">
                        <div className="col-span-2">
                          <label className="block text-sm font-medium text-gray-700">Product</label>
                          <select
                            value={item.product_id}
                            onChange={(e) => updateBOMItem(index, 'product_id', parseInt(e.target.value))}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                          >
                            <option value={0}>Select Product</option>
                            {products.map((product) => (
                              <option key={product.product_id} value={product.product_id}>
                                {product.product_name || product.name} ({product.product_code || product.code})
                              </option>
                            ))}
                          </select>
                          {formErrors[`item_${index}_product`] && <p className="text-red-500 text-xs mt-1">{formErrors[`item_${index}_product`]}</p>}
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700">Quantity</label>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={item.quantity}
                            onChange={(e) => updateBOMItem(index, 'quantity', parseFloat(e.target.value) || 0)}
                            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                          />
                          {formErrors[`item_${index}_quantity`] && <p className="text-red-500 text-xs mt-1">{formErrors[`item_${index}_quantity`]}</p>}
                        </div>

                        <div className="flex items-end">
                          <button
                            type="button"
                            onClick={() => removeBOMItem(index)}
                            className="px-3 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 hover:bg-red-50"
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </div>
                      </div>

                      <div className="mt-4">
                        <label className="block text-sm font-medium text-gray-700">Notes</label>
                        <input
                          type="text"
                          value={item.notes || ''}
                          onChange={(e) => updateBOMItem(index, 'notes', e.target.value)}
                          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </div>
                    </div>
                  ))}

                  {formErrors.bom_items && <p className="text-red-500 text-xs mt-1">{formErrors.bom_items}</p>}
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
                    disabled={createBOM.isPending || updateBOM.isPending}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {createBOM.isPending || updateBOM.isPending
                      ? 'Saving...'
                      : editingBOM
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
      {viewingBOM && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                BOM Details: {viewingBOM.bom_name || viewingBOM.name}
              </h3>
              
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-700">BOM Code</p>
                    <p className="text-sm text-gray-900">{viewingBOM.bom_code || viewingBOM.code}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-700">Version</p>
                    <p className="text-sm text-gray-900">{viewingBOM.version}</p>
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium text-gray-700">Product</p>
                  <p className="text-sm text-gray-900">
                    {viewingBOM.product?.product_name} ({viewingBOM.product?.product_code})
                  </p>
                </div>

                {viewingBOM.description && (
                  <div>
                    <p className="text-sm font-medium text-gray-700">Description</p>
                    <p className="text-sm text-gray-900">{viewingBOM.description}</p>
                  </div>
                )}

                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">BOM Items</p>
                  <div className="border border-gray-300 rounded-md">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {viewingBOM.bom_items?.map((item, index) => (
                          <tr key={`view-item-${item.product_id}-${index}`}>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {item.product?.product_name} ({item.product?.product_code})
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {item.quantity}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {item.notes || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={() => setViewingBOM(null)}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Cost Calculation Modal */}
      {showCostModal && costCalculation && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-50">
          <div className="relative top-20 mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Cost Calculation
              </h3>
              
              <div className="space-y-4">
                <div className="bg-green-50 p-4 rounded-md">
                  <p className="text-lg font-medium text-green-900">
                    Total Cost: ${costCalculation.total_cost.toFixed(2)}
                  </p>
                </div>

                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">Detailed Costs</p>
                  <div className="border border-gray-300 rounded-md">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Product</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Unit Cost</th>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Total Cost</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {costCalculation.detailed_costs.map((cost, index) => (
                          <tr key={`cost-${cost.product_name}-${index}`}>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {cost.product_name}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              {cost.quantity}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              ${cost.unit_cost.toFixed(2)}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-900">
                              ${cost.total_cost.toFixed(2)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={() => {
                    setShowCostModal(false);
                    setCostCalculationId(null);
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