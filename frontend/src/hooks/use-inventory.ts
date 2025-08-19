import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';
import {
  InventoryItem,
  InventoryFilters,
  PaginatedResponse,
  StockInRequest,
  StockOutRequest,
  StockOutResponse,
  StockAdjustmentRequest,
  StockAvailabilityResponse,
  StockMovement,
} from '@/types/api';

export function useInventoryItems(filters?: InventoryFilters) {
  return useQuery({
    queryKey: ['inventory-items', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<InventoryItem>>(
        '/inventory/items',
        filters
      );
      return response.data;
    },
  });
}

export function useStockAvailability(productId: number, warehouseId?: number) {
  return useQuery({
    queryKey: ['stock-availability', productId, warehouseId],
    queryFn: async () => {
      const params = warehouseId ? { warehouse_id: warehouseId } : undefined;
      const response = await apiClient.get<StockAvailabilityResponse>(
        `/inventory/availability/${productId}`,
        params
      );
      return response.data;
    },
    enabled: !!productId,
  });
}

export function useStockMovements(filters?: { inventory_item_id?: number; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ['stock-movements', filters],
    queryFn: async () => {
      const response = await apiClient.get<PaginatedResponse<StockMovement>>(
        '/inventory/movements',
        filters
      );
      return response.data;
    },
  });
}

export function useStockIn() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: StockInRequest) => {
      const response = await apiClient.post<InventoryItem>('/inventory/stock-in', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-items'] });
      queryClient.invalidateQueries({ queryKey: ['stock-availability'] });
      queryClient.invalidateQueries({ queryKey: ['stock-movements'] });
      // Invalidate BOM cost calculations since stock changes affect FIFO costing
      queryClient.invalidateQueries({ queryKey: ['boms'], predicate: (query) => {
        return query.queryKey.includes('cost-calculation');
      }});
    },
  });
}

export function useStockOut() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: StockOutRequest) => {
      const response = await apiClient.post<StockOutResponse>('/inventory/stock-out', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-items'] });
      queryClient.invalidateQueries({ queryKey: ['stock-availability'] });
      queryClient.invalidateQueries({ queryKey: ['stock-movements'] });
      // Invalidate BOM cost calculations since stock changes affect FIFO costing
      queryClient.invalidateQueries({ queryKey: ['boms'], predicate: (query) => {
        return query.queryKey.includes('cost-calculation');
      }});
    },
  });
}

export function useStockAdjustment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: StockAdjustmentRequest) => {
      const response = await apiClient.post<InventoryItem>('/inventory/adjustment', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['inventory-items'] });
      queryClient.invalidateQueries({ queryKey: ['stock-availability'] });
      queryClient.invalidateQueries({ queryKey: ['stock-movements'] });
      // Invalidate BOM cost calculations since stock changes affect FIFO costing
      queryClient.invalidateQueries({ queryKey: ['boms'], predicate: (query) => {
        return query.queryKey.includes('cost-calculation');
      }});
    },
  });
}

export function useCriticalStock() {
  return useQuery({
    queryKey: ['critical-stock'],
    queryFn: async () => {
      const response = await apiClient.get<InventoryItem[]>('/inventory/critical-stock');
      return response.data;
    },
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}