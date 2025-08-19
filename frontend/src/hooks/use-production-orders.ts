import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { 
  ProductionOrder, 
  CreateProductionOrderRequest, 
  UpdateProductionOrderRequest, 
  ProductionOrderFilters, 
  PaginatedResponse 
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