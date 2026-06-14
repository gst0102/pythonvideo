const API_BASE = (import.meta.env.VITE_API_BASE_URL || "https://api.lifelove.top").replace(/\/$/, "");

export interface UserAccount {
  total_points: number;
  withdrawable_points: number;
  frozen_points: number;
  consumable_points: number;
}

export interface NetdiskResource {
  id: string;
  title: string;
  category: string;
  pan: string;
  level: "normal" | "featured" | "official" | string;
  cost_points: number;
  verified_at: string;
  downloads: number;
  favorites: number;
  description: string;
  is_active: boolean;
  quality_score?: number;
  uploader_credit_level?: string;
  uploader_credit_score?: number;
  uploader_nickname?: string;
  uploader_avatar?: string;
  valid_days?: number;
  report_count?: number;
  invalid_count?: number;
}

export interface ResourceListResponse {
  resources: NetdiskResource[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface NetdiskResourceAccess {
  unlocked: boolean;
  ledger_id: string;
  points_delta: number;
  link: string;
  extract_code: string;
  unzip_code: string;
}

export interface ResourceDetailResponse {
  resource: NetdiskResource;
}

export interface ResourceAccessResponse {
  resource: NetdiskResource;
  access: NetdiskResourceAccess;
  account: UserAccount;
}

export interface ResourceUnlockResponse {
  resource: NetdiskResource;
  unlock: NetdiskResourceAccess;
  account: UserAccount;
}

export interface NetdiskNotification {
  id: string;
  notice_type: string;
  title: string;
  content: string;
  related_type: string;
  related_id: string;
  status: string;
  created_at: string;
}

export interface NotificationListResponse {
  notifications: NetdiskNotification[];
  unread_count: number;
}

export interface LoginResponse {
  token: string;
  is_new_user: boolean;
  user: {
    id: string;
    openid: string;
    nickname: string;
    avatar: string;
    account: UserAccount;
    credit_score: number;
    contribution_score: number;
    credit_level: string;
    risk_level: string;
    credit_restore_tip: string;
  };
}

export interface UserProfileResponse {
  id: string;
  openid: string;
  nickname: string;
  avatar: string;
  invite_code: string;
  account: UserAccount;
  credit_score: number;
  contribution_score: number;
  credit_level: string;
  risk_level: string;
  credit_restore_tip: string;
}

export interface FavoriteListResponse {
  favorites: Array<{
    resource: NetdiskResource;
    favorite_at: string;
    favorited: boolean;
  }>;
}

export interface FavoriteResponse {
  resource: NetdiskResource;
  favorite_at?: string;
  favorited: boolean;
}

export interface RepairResponse {
  repair: {
    id: string;
    resource_id: string;
    resource_title: string;
    mode: string;
    status: string;
    audit_note: string;
    note: string;
  };
}

export interface UploadListResponse {
  uploads: Array<{
    id: string;
    title: string;
    category: string;
    pan: string;
    status: string;
    reward_points: number;
    reward_released_points: number;
    valid_days_rewarded: number;
    audit_note: string;
    created_at: string;
  }>;
}

export interface RepairListResponse {
  repairs: Array<{
    id: string;
    resource_id: string;
    resource_title: string;
    mode: "repair" | "report" | string;
    pan: string;
    status: string;
    reward_points: number;
    audit_note: string;
    note: string;
    created_at: string;
  }>;
}

export interface PointsLedgerItem {
  id: string;
  change_type: string;
  source: string;
  availability: string;
  points_delta: number;
  balance_withdrawable_after: number;
  balance_frozen_after: number;
  balance_consumable_after: number;
  related_type?: string;
  related_id?: string;
  remark?: string;
  created_at: string;
}

export interface PointsLedgerResponse {
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  account: UserAccount;
  items: PointsLedgerItem[];
}

const getToken = () => {
  return uni.getStorageSync("token") || uni.getStorageSync("access_token") || "";
};

export const hasLoginToken = () => Boolean(getToken());

export const setToken = (token: string) => {
  uni.setStorageSync("token", token);
  uni.setStorageSync("access_token", token);
};

export const ensureWechatLogin = async () => {
  const existing = getToken();
  if (existing) return existing;
  const code = await new Promise<string>((resolve, reject) => {
    uni.login({
      provider: "weixin",
      success: (res) => {
        if (res.code) {
          resolve(res.code);
          return;
        }
        reject(new Error("微信登录失败"));
      },
      fail: () => reject(new Error("微信登录失败"))
    });
  });
  const data = await request<LoginResponse>("/user/login", {
    method: "POST",
    data: {
      code,
      nickname: uni.getStorageSync("nickname") || "",
      avatar: uni.getStorageSync("avatar") || ""
    }
  });
  setToken(data.token);
  return data.token;
};

export const request = <T>(url: string, options: UniApp.RequestOptions = {}) => {
  return new Promise<T>((resolve, reject) => {
    const token = getToken();
    uni.request({
      ...options,
      url: `${API_BASE}${url}`,
      header: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.header || {})
      },
      success: (res) => {
        const data: any = res.data || {};
        if (data.code === 200 || data.code === 0) {
          resolve((data.data ?? data) as T);
          return;
        }
        reject(new Error(data.msg || data.message || "请求失败"));
      },
      fail: () => reject(new Error("后端服务暂不可用"))
    });
  });
};

export const getNetdiskNotifications = () => {
  return request<NotificationListResponse>("/netdisk/notifications");
};

export const markNetdiskNotificationRead = (id: string) => {
  return request<NetdiskNotification>(`/netdisk/notifications/${id}/read`, { method: "POST" });
};

export const getNetdiskResources = (params: Record<string, string | number | undefined> = {}) => {
  const query = Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(String(params[key]))}`)
    .join("&");
  return request<ResourceListResponse>(`/netdisk/resources${query ? `?${query}` : ""}`);
};

export const getNetdiskResourceDetail = (id: string) => {
  return request<ResourceDetailResponse>(`/netdisk/resources/${id}`);
};

export const getNetdiskResourceAccess = (id: string) => {
  return request<ResourceAccessResponse>(`/netdisk/resources/${id}/access`);
};

export const unlockNetdiskResource = (id: string) => {
  return request<ResourceUnlockResponse>(`/netdisk/resources/${id}/unlock`, { method: "POST" });
};

export const getNetdiskFavorites = () => {
  return request<FavoriteListResponse>("/netdisk/favorites");
};

export const getUserProfile = () => {
  return request<UserProfileResponse>("/user/profile");
};

export const getMyNetdiskUploads = () => {
  return request<UploadListResponse>("/netdisk/uploads/mine");
};

export const getMyNetdiskRepairs = () => {
  return request<RepairListResponse>("/netdisk/repairs/mine");
};

export const getPointsLedger = (params: Record<string, string | number | undefined> = {}) => {
  const query = Object.keys(params)
    .filter((key) => params[key] !== undefined && params[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(String(params[key]))}`)
    .join("&");
  return request<PointsLedgerResponse>(`/points/ledger${query ? `?${query}` : ""}`);
};

export const favoriteNetdiskResource = (id: string) => {
  return request<FavoriteResponse>(`/netdisk/resources/${id}/favorite`, { method: "POST" });
};

export const unfavoriteNetdiskResource = (id: string) => {
  return request<FavoriteResponse>(`/netdisk/resources/${id}/favorite`, { method: "DELETE" });
};

export const reportNetdiskResource = (resource: NetdiskResource, note: string) => {
  return request<RepairResponse>("/netdisk/repairs", {
    method: "POST",
    data: {
      resource_id: resource.id,
      mode: "report",
      pan: resource.pan,
      note
    }
  });
};
