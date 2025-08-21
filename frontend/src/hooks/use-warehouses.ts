import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import { Warehouse, CreateWarehouseRequest, WarehouseFilters, PaginatedResponse } from '@/types/api';

export function useWarehouses(filters?: WarehouseFilters) {
  return useQuery({
    queryKey: ['warehouses', filters],
    queryFn: async () => {
      // Map frontend 'type' parameter to backend 'warehouse_type'
      const backendParams = filters ? {
        ...filters,
        warehouse_type: filters.type,
        type: undefined // Remove the type field
      } : undefined;
      
      const response = await apiClient.get<PaginatedResponse<Warehouse>>(
        '/master-data/warehouses',
        backendParams
      );
      return response.data;
    },
  });
}

export function useWarehouse(id: number) {
  return useQuery({
    queryKey: ['warehouses', id],
    queryFn: async () => {
      const response = await apiClient.get<Warehouse>(`/master-data/warehouses/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateWarehouse() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: CreateWarehouseRequest) => {
      const response = await apiClient.post<Warehouse>('/master-data/warehouses', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
    },
  });
}

export function useUpdateWarehouse() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<CreateWarehouseRequest> }) => {
      const response = await apiClient.put<Warehouse>(`/master-data/warehouses/${id}`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
      queryClient.invalidateQueries({ queryKey: ['warehouses', data?.id] });
    },
  });
}

export function useDeleteWarehouse() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.delete(`/master-data/warehouses/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['warehouses'] });
    },
  });
}