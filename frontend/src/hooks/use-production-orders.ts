import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { 
  ProductionOrder, 
  CreateProductionOrderRequest,
  CreateProductionOrderWithAnalysisRequest,
  CreateProductionOrderWithAnalysisResponse,
  UpdateProductionOrderRequest, 
  ProductionOrderFilters, 
  PaginatedResponse,
  ProductionOrderStockAnalysis,
  EnhancedProductionOrder,
  ProductionOrderComponent,
  UpdateComponentStatusRequest,
  StockReservation
} from '@/types/api';

export function useProductionOrders(filters?: ProductionOrderFilters) {
  return useQuery({
    queryKey: ['production-orders', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<ProductionOrder>>(
        '/production-orders/',
        filters
      );
      return response.data;
    },
  });
}

export function useProductionOrder(id: number) {
  return useQuery({
    queryKey: ['production-orders', id],
    queryFn: async () => {
      const response = await apiClient.get<ProductionOrder>(`/production-orders/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateProductionOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateProductionOrderRequest) => {
      const response = await apiClient.post<ProductionOrder>('/production-orders/', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['production-orders'] });
    },
  });
}

export function useUpdateProductionOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: UpdateProductionOrderRequest }) => {
      const response = await apiClient.put<ProductionOrder>(`/production-orders/${id}`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['production-orders'] });
      queryClient.invalidateQueries({ queryKey: ['production-orders', data?.production_order_id || data?.id] });
    },
  });
}

export function useDeleteProductionOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete(`/production-orders/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['production-orders'] });
    },
  });
}

// Advanced MRP hooks

// Stock analysis for production orders
export function useProductionOrderStockAnalysis(id: number) {
  return useQuery({
    queryKey: ['production-orders', id, 'stock-analysis'],
    queryFn: async () => {
      const response = await apiClient.get<ProductionOrderStockAnalysis>(
        `/production-orders/${id}/stock-analysis`
      );
      return response.data;
    },
    enabled: !!id,
  });
}

// Advanced production order creation with analysis
export function useCreateProductionOrderWithAnalysis() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateProductionOrderWithAnalysisRequest) => {
      const response = await apiClient.post<CreateProductionOrderWithAnalysisResponse>(
        '/production-orders/create-with-analysis',
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['production-orders'] });
    },
  });
}

// Get enhanced production order with components and reservations
export function useEnhancedProductionOrder(id: number) {
  return useQuery({
    queryKey: ['production-orders', id, 'enhanced'],
    queryFn: async () => {
      const response = await apiClient.get<EnhancedProductionOrder>(
        `/production-orders/${id}/enhanced`
      );
      return response.data;
    },
    enabled: !!id,
  });
}

// Component management
export function useProductionOrderComponents(productionOrderId: number) {
  return useQuery({
    queryKey: ['production-orders', productionOrderId, 'components'],
    queryFn: async () => {
      const response = await apiClient.get<ProductionOrderComponent[]>(
        `/production-orders/${productionOrderId}/components`
      );
      return response.data;
    },
    enabled: !!productionOrderId,
  });
}

export function useUpdateComponentStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ 
      productionOrderId, 
      data 
    }: { 
      productionOrderId: number; 
      data: UpdateComponentStatusRequest 
    }) => {
      const response = await apiClient.put(
        `/production-orders/${productionOrderId}/components/${data.component_id}`,
        data
      );
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: ['production-orders', variables.productionOrderId, 'components'] 
      });
      queryClient.invalidateQueries({ 
        queryKey: ['production-orders', variables.productionOrderId, 'enhanced'] 
      });
    },
  });
}

// Stock reservations
export function useProductionOrderReservations(productionOrderId: number) {
  return useQuery({
    queryKey: ['production-orders', productionOrderId, 'reservations'],
    queryFn: async () => {
      const response = await apiClient.get<StockReservation[]>(
        `/production-orders/${productionOrderId}/reservations`
      );
      return response.data;
    },
    enabled: !!productionOrderId,
  });
}

// Stock analysis without creating production order
export function useAnalyzeStockAvailability() {
  return useMutation({
    mutationFn: async (data: { bom_id: number; warehouse_id: number; quantity_to_produce: number }) => {
      const response = await apiClient.post<ProductionOrderStockAnalysis>('/production-orders/analyze-stock', data);
      return response.data;
    },
  });
}