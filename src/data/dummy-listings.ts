export type ListingPlatform = "instagram" | "facebook" | "reddit";
export type ListingStatus = "available" | "unknown" | "sold";
export type ListingAspect = "portrait" | "square" | "landscape" | "tall";

export type DummyListing = {
  id: string;
  title: string;
  description: string;
  price: number | null;
  platform: ListingPlatform;
  status: ListingStatus;
  category: string;
  brand: string;
  condition: string;
  location: string;
  seller: string;
  postedLabel: string;
  imageUrl: string;
  imagePageUrl: string;
  imageAlt: string;
  imageAspect: ListingAspect;
  tags: string[];
};

export const collections = [
  { slug: "all", label: "Semua", mark: "00" },
  { slug: "laptop", label: "Laptop", mark: "LP" },
  { slug: "gpu", label: "GPU", mark: "GX" },
  { slug: "pc-build", label: "PC Rakitan", mark: "PC" },
  { slug: "peripheral", label: "Periferal", mark: "PR" },
  { slug: "monitor", label: "Monitor", mark: "MN" },
  { slug: "gaming", label: "Gaming", mark: "GM" },
] as const;

export const platformMeta: Record<
  ListingPlatform,
  { label: string; short: string; accent: string; description: string }
> = {
  instagram: {
    label: "Instagram",
    short: "IG",
    accent: "coral",
    description: "Listing dari akun jual-beli dan toko preloved yang dipantau.",
  },
  facebook: {
    label: "Facebook",
    short: "FB",
    accent: "blue",
    description: "Temuan Marketplace dari penjual publik di berbagai kota.",
  },
  reddit: {
    label: "Reddit",
    short: "R/",
    accent: "orange",
    description: "Post WTS komputer dan periferal dari komunitas Indonesia.",
  },
};

const img = (id: string) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=1200&q=82`;

export const dummyListings: DummyListing[] = [
  {
    id: "recon-001",
    title: "RTX 3090 Founders Edition 24GB",
    description:
      "Unit mulus, pemakaian render ringan. Box lengkap dan bisa test sampai puas.",
    price: 10900000,
    platform: "instagram",
    status: "available",
    category: "gpu",
    brand: "NVIDIA",
    condition: "Bekas — sangat baik",
    location: "Jakarta Selatan",
    seller: "pixel.parts",
    postedLabel: "8 menit lalu",
    imageUrl: img("photo-1752179634046-5159d1b13f6f"),
    imagePageUrl:
      "https://unsplash.com/photos/a-close-up-of-an-rtx-3090-graphics-card-FAdPUFutzb0",
    imageAlt: "Close-up kartu grafis RTX 3090",
    imageAspect: "portrait",
    tags: ["rtx", "graphics card", "render"],
  },
  {
    id: "recon-002",
    title: "Desk setup dual monitor 27 inch",
    description:
      "Dijual sepaket dua monitor IPS, arm North Bayou, keyboard, dan lampu meja.",
    price: 4750000,
    platform: "facebook",
    status: "available",
    category: "monitor",
    brand: "LG",
    condition: "Bekas — baik",
    location: "Bandung",
    seller: "Raka Pratama",
    postedLabel: "14 menit lalu",
    imageUrl: img("photo-1634891392987-e91db6bf9557"),
    imagePageUrl:
      "https://unsplash.com/photos/two-computer-monitors-sitting-on-top-of-a-white-desk-wcoXr9o83o8",
    imageAlt: "Dua monitor komputer di atas meja putih",
    imageAspect: "landscape",
    tags: ["monitor", "dual screen", "desk setup"],
  },
  {
    id: "recon-003",
    title: "Keychron K3 low-profile mechanical",
    description:
      "Brown switch, RGB normal, keycap lengkap. Bonus travel pouch dan kabel braided.",
    price: 890000,
    platform: "reddit",
    status: "available",
    category: "peripheral",
    brand: "Keychron",
    condition: "Bekas — sangat baik",
    location: "Yogyakarta",
    seller: "u/analogweekend",
    postedLabel: "22 menit lalu",
    imageUrl: img("photo-1664441156356-574882b11b6a"),
    imagePageUrl:
      "https://unsplash.com/photos/a-close-up-of-a-computer-keyboard-U-VLVzcc68M",
    imageAlt: "Keyboard mekanikal Keychron dari dekat",
    imageAspect: "square",
    tags: ["keyboard", "mechanical", "keychron"],
  },
  {
    id: "recon-004",
    title: "MacBook Air M1 8/256 Space Gray",
    description:
      "Battery health 91%, body bersih, layar aman. Unit, charger, dan box bawaan.",
    price: 8450000,
    platform: "instagram",
    status: "available",
    category: "laptop",
    brand: "Apple",
    condition: "Bekas — sangat baik",
    location: "Surabaya",
    seller: "secondbyte.id",
    postedLabel: "31 menit lalu",
    imageUrl: img("photo-1594972765410-9fe8c0e4e984"),
    imagePageUrl:
      "https://unsplash.com/photos/macbook-air-on-white-table-noW0zN8Vb4E",
    imageAlt: "MacBook Air di atas meja putih",
    imageAspect: "tall",
    tags: ["macbook", "apple silicon", "ultrabook"],
  },
  {
    id: "recon-005",
    title: "PC Ryzen 7 + RTX, clean white build",
    description:
      "Ryzen 7 5800X, RAM 32GB, RTX 3070, SSD NVMe 1TB. Siap kerja dan main.",
    price: 15750000,
    platform: "facebook",
    status: "available",
    category: "pc-build",
    brand: "Custom",
    condition: "Bekas — sangat baik",
    location: "Tangerang Selatan",
    seller: "Faisal Build",
    postedLabel: "42 menit lalu",
    imageUrl: img("photo-1763905180930-892ee8d37ea6"),
    imagePageUrl:
      "https://unsplash.com/photos/computer-setup-with-monitor-keyboard-and-webcam-dSFV8clfe98",
    imageAlt: "Setup komputer desktop dengan monitor dan keyboard",
    imageAspect: "portrait",
    tags: ["pc build", "ryzen", "rtx 3070"],
  },
  {
    id: "recon-006",
    title: "Headset gaming wireless low latency",
    description:
      "Dongle lengkap, earcup baru diganti. Baterai sekitar 25 jam per pengisian.",
    price: 1250000,
    platform: "instagram",
    status: "unknown",
    category: "peripheral",
    brand: "SteelSeries",
    condition: "Bekas — baik",
    location: "Depok",
    seller: "gearagain",
    postedLabel: "1 jam lalu",
    imageUrl: img("photo-1648241776507-7e3ae32698e6"),
    imagePageUrl:
      "https://unsplash.com/photos/a-pair-of-headphones-sitting-on-top-of-a-desk-ScLBbRi1OJo",
    imageAlt: "Headset gaming di atas meja",
    imageAspect: "landscape",
    tags: ["headset", "wireless", "gaming"],
  },
  {
    id: "recon-007",
    title: "Minimal workspace set — monitor + laptop",
    description:
      "Monitor 24 inch, laptop stand aluminium, dan USB-C dock. Bisa ambil satuan.",
    price: 3200000,
    platform: "reddit",
    status: "available",
    category: "monitor",
    brand: "Dell",
    condition: "Bekas — baik",
    location: "Jakarta Pusat",
    seller: "u/sundaydeclutter",
    postedLabel: "1 jam lalu",
    imageUrl: img("photo-1639506060085-2a01a8a84c34"),
    imagePageUrl:
      "https://unsplash.com/photos/a-desk-with-a-laptop-and-a-monitor-on-it-TTHm86CTwXQ",
    imageAlt: "Meja minimalis dengan laptop dan monitor",
    imageAspect: "square",
    tags: ["monitor", "dock", "workspace"],
  },
  {
    id: "recon-008",
    title: "ASUS TUF A15 Ryzen 7 RTX 3060",
    description:
      "RAM 16GB, SSD 512GB. Suhu aman, keyboard normal, minus pemakaian wajar.",
    price: 11200000,
    platform: "facebook",
    status: "available",
    category: "laptop",
    brand: "ASUS",
    condition: "Bekas — baik",
    location: "Semarang",
    seller: "Bagas Nugroho",
    postedLabel: "2 jam lalu",
    imageUrl: img("photo-1716681863790-45ee0db408ff"),
    imagePageUrl:
      "https://unsplash.com/photos/a-laptop-computer-sitting-on-top-of-a-desk-JyuI90QJ4ww",
    imageAlt: "Laptop di meja kerja dengan monitor",
    imageAspect: "portrait",
    tags: ["gaming laptop", "asus tuf", "rtx 3060"],
  },
  {
    id: "recon-009",
    title: "Gaming room bundle RGB",
    description:
      "Meja, dual monitor, speaker, mechanical keyboard, dan ambient light satu paket.",
    price: 7900000,
    platform: "instagram",
    status: "available",
    category: "gaming",
    brand: "Mixed",
    condition: "Bekas — sangat baik",
    location: "Bekasi",
    seller: "setup.swap",
    postedLabel: "2 jam lalu",
    imageUrl: img("photo-1675049626914-b2e051e92f23"),
    imagePageUrl:
      "https://unsplash.com/photos/a-computer-desk-with-two-monitors-and-a-keyboard-FpTTnUxS45g",
    imageAlt: "Setup gaming merah dengan dua monitor",
    imageAspect: "tall",
    tags: ["gaming room", "rgb", "bundle"],
  },
  {
    id: "recon-010",
    title: "RTX 3070 Ti triple fan",
    description:
      "Garansi distributor masih jalan. Tidak pernah mining, segel dan fan aman.",
    price: 6200000,
    platform: "reddit",
    status: "sold",
    category: "gpu",
    brand: "Gigabyte",
    condition: "Bekas — baik",
    location: "Malang",
    seller: "u/framechaser",
    postedLabel: "3 jam lalu",
    imageUrl: img("photo-1752179634046-5159d1b13f6f"),
    imagePageUrl:
      "https://unsplash.com/photos/a-close-up-of-an-rtx-3090-graphics-card-FAdPUFutzb0",
    imageAlt: "Kartu grafis NVIDIA dari dekat",
    imageAspect: "landscape",
    tags: ["gpu", "rtx 3070 ti", "gigabyte"],
  },
  {
    id: "recon-011",
    title: "Mini ITX creator build",
    description:
      "Casing ringkas, Ryzen 5, RAM 32GB, storage 2TB. Hening untuk meja kecil.",
    price: 9800000,
    platform: "facebook",
    status: "available",
    category: "pc-build",
    brand: "Custom",
    condition: "Bekas — sangat baik",
    location: "Bogor",
    seller: "Dimas Arya",
    postedLabel: "3 jam lalu",
    imageUrl: img("photo-1763905180930-892ee8d37ea6"),
    imagePageUrl:
      "https://unsplash.com/photos/computer-setup-with-monitor-keyboard-and-webcam-dSFV8clfe98",
    imageAlt: "Komputer desktop ringkas di meja kerja",
    imageAspect: "square",
    tags: ["mini itx", "creator pc", "small form factor"],
  },
  {
    id: "recon-012",
    title: "ThinkPad X1 Carbon Gen 9",
    description:
      "i7, RAM 16GB, SSD 1TB. Keyboard nyaman, layar 2K, baterai masih sehat.",
    price: 9850000,
    platform: "instagram",
    status: "available",
    category: "laptop",
    brand: "Lenovo",
    condition: "Bekas — sangat baik",
    location: "Jakarta Barat",
    seller: "notebook.archive",
    postedLabel: "4 jam lalu",
    imageUrl: img("photo-1594972765410-9fe8c0e4e984"),
    imagePageUrl:
      "https://unsplash.com/photos/macbook-air-on-white-table-noW0zN8Vb4E",
    imageAlt: "Laptop tipis berwarna gelap di atas meja",
    imageAspect: "portrait",
    tags: ["thinkpad", "business laptop", "x1 carbon"],
  },
  {
    id: "recon-013",
    title: "Custom keyboard 75% aluminium",
    description:
      "Gasket mount, linear switch lubed, PBT keycaps. Suara thock, siap pakai.",
    price: 2150000,
    platform: "reddit",
    status: "available",
    category: "peripheral",
    brand: "Custom",
    condition: "Bekas — sangat baik",
    location: "Denpasar",
    seller: "u/thocktherapy",
    postedLabel: "5 jam lalu",
    imageUrl: img("photo-1664441156356-574882b11b6a"),
    imagePageUrl:
      "https://unsplash.com/photos/a-close-up-of-a-computer-keyboard-U-VLVzcc68M",
    imageAlt: "Keyboard mekanikal berwarna ungu",
    imageAspect: "tall",
    tags: ["custom keyboard", "75 percent", "mechanical"],
  },
  {
    id: "recon-014",
    title: "Ultrawide 34 inch 144Hz",
    description:
      "Panel VA, tidak ada dead pixel. Lengkap stand dan box, prefer ambil langsung.",
    price: 5100000,
    platform: "facebook",
    status: "unknown",
    category: "monitor",
    brand: "Xiaomi",
    condition: "Bekas — baik",
    location: "Solo",
    seller: "Naufal Tech",
    postedLabel: "5 jam lalu",
    imageUrl: img("photo-1634891392987-e91db6bf9557"),
    imagePageUrl:
      "https://unsplash.com/photos/two-computer-monitors-sitting-on-top-of-a-white-desk-wcoXr9o83o8",
    imageAlt: "Monitor ultrawide pada meja minimalis",
    imageAspect: "landscape",
    tags: ["ultrawide", "144hz", "monitor"],
  },
  {
    id: "recon-015",
    title: "Steam Deck OLED 512GB",
    description:
      "Fullset, tempered glass terpasang. Bonus hardcase dan microSD 256GB.",
    price: 8900000,
    platform: "instagram",
    status: "available",
    category: "gaming",
    brand: "Valve",
    condition: "Bekas — seperti baru",
    location: "Makassar",
    seller: "handheld.hub",
    postedLabel: "6 jam lalu",
    imageUrl: img("photo-1675049626914-b2e051e92f23"),
    imagePageUrl:
      "https://unsplash.com/photos/a-computer-desk-with-two-monitors-and-a-keyboard-FpTTnUxS45g",
    imageAlt: "Perangkat gaming dalam setup meja gelap",
    imageAspect: "square",
    tags: ["steam deck", "handheld", "oled"],
  },
  {
    id: "recon-016",
    title: "Workstation monitor arm bundle",
    description:
      "Dua monitor 24 inch, dual arm gas spring, dan docking station Thunderbolt.",
    price: 5900000,
    platform: "reddit",
    status: "available",
    category: "monitor",
    brand: "Dell",
    condition: "Bekas — baik",
    location: "Tangerang",
    seller: "u/deskreset",
    postedLabel: "7 jam lalu",
    imageUrl: img("photo-1639506060085-2a01a8a84c34"),
    imagePageUrl:
      "https://unsplash.com/photos/a-desk-with-a-laptop-and-a-monitor-on-it-TTHm86CTwXQ",
    imageAlt: "Monitor dan laptop pada workstation minimalis",
    imageAspect: "portrait",
    tags: ["workstation", "monitor arm", "thunderbolt"],
  },
  {
    id: "recon-017",
    title: "ROG Zephyrus G14 compact gaming",
    description:
      "Ryzen 9, RTX 4060, RAM 32GB. Ringkas untuk kerja mobile dan gaming.",
    price: 21400000,
    platform: "facebook",
    status: "available",
    category: "laptop",
    brand: "ASUS",
    condition: "Bekas — seperti baru",
    location: "Jakarta Utara",
    seller: "Kevin Wijaya",
    postedLabel: "8 jam lalu",
    imageUrl: img("photo-1716681863790-45ee0db408ff"),
    imagePageUrl:
      "https://unsplash.com/photos/a-laptop-computer-sitting-on-top-of-a-desk-JyuI90QJ4ww",
    imageAlt: "Laptop gaming di meja kerja",
    imageAspect: "landscape",
    tags: ["zephyrus", "rtx 4060", "gaming laptop"],
  },
  {
    id: "recon-018",
    title: "Sony wireless headset + stand",
    description:
      "Suara dan ANC normal. Earpad baru, bonus stand aluminium dan pouch.",
    price: 1850000,
    platform: "instagram",
    status: "sold",
    category: "peripheral",
    brand: "Sony",
    condition: "Bekas — baik",
    location: "Bandung",
    seller: "audio.secondlife",
    postedLabel: "9 jam lalu",
    imageUrl: img("photo-1648241776507-7e3ae32698e6"),
    imagePageUrl:
      "https://unsplash.com/photos/a-pair-of-headphones-sitting-on-top-of-a-desk-ScLBbRi1OJo",
    imageAlt: "Headset wireless di meja gaming",
    imageAspect: "tall",
    tags: ["sony", "headset", "wireless"],
  },
];

export function formatRupiah(value: number | null) {
  if (value === null) return "Harga belum terbaca";

  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}
