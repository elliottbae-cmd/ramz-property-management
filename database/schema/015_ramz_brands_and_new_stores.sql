-- 015: Update existing Freddy's stores with brand and add Schlotzsky's + Popeyes stores

-- Update all existing Freddy's stores with brand
UPDATE stores SET brand = 'Freddys' WHERE client_id = 'a0000000-0000-0000-0000-000000000001';

-- Insert Schlotzsky's stores
INSERT INTO stores (client_id, store_number, name, address, city, state, region, brand) VALUES
('a0000000-0000-0000-0000-000000000001', '1140', 'Camp Bowie', '6000 Camp Bowie Blvd', 'Camp Bowie', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1139', 'Pantego', '2504 W Park Row Dr', 'Pantego', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '3718', 'Burleson', '705 SW Wilshire Blvd', 'Burleson', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '3716', 'Fort Worth', '3530 Northwest Center Dr', 'Fort Worth', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '104030', 'Bentonville', '1626 E Centerton Blvd', 'Bentonville', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '104026', 'Derby KS', '2250 N Rock Rd', 'Derby', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1560', 'Fayetteville', '2548 N College Ave', 'Fayetteville', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1417', 'Ft. Smith', '7010 Rogers Ave', 'Ft. Smith', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '100895', 'Gilmer', '720 US Hwy 271 N', 'Gilmer', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '100855', 'Henderson', '419 S US-79', 'Henderson', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '2877', 'Huntsville', '118 Interstate 45 S', 'Huntsville', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '2150', 'Lufkin', '4601 S Medford Dr', 'Lufkin', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '104028', 'Mountain Home', '1012 Hwy 62 E', 'Mountain Home', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1768', 'Rogers', '2709 W Walnut St', 'Rogers', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1030', 'E Central', '6507 E. Central Ave.', 'Wichita', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1813', 'Salina', '2480 S 9th St', 'Salina', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '104032', 'Siloam Springs', '440 US-412 W', 'Siloam Springs', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '912', 'Springdale', '1919 W Sunset Ave', 'Springdale', 'AR', 'Arkansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1729', 'Springfield (Glenstone)', '1316 N Glenstone Ave', 'Springfield', 'MO', 'Missouri', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '100232', 'Sulphur Springs', '1050 Gilmer Street', 'Sulphur Springs', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1870', 'Terrell', '1610 Tx Hwy 34', 'Terrell', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1636', 'Waco (I-35)', '1508 I-35', 'Waco', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1372', 'Waco (Valley Mills)', '625 N Valley Mills Dr', 'Waco', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1029', 'Pawnee', '1334 W. Pawnee ST', 'Wichita', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '962', 'W Central', '8710 W Central', 'Wichita', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '2751', 'Coppell', '135 S Denton Tap Rd', 'Coppell', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1212', 'Lewisville', '450 E Round Grove Rd, Ste 101', 'Lewisville', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '101336', 'Murphy', '350 W FM544', 'Murphy', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '101493', 'Wylie', '330 South Highway 78, Ste 100', 'Wylie', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '1491', 'Springfield (Campbell)', '4132 S Campbell Ave', 'Springfield', 'MO', 'Missouri', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '103237', 'Greenwich', '2692 N Greenwich, Ste 200', 'Wichita', 'KS', 'Kansas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '102041', 'Kilgore', '1211 N. Kilgore Street', 'Kilgore', 'TX', 'Texas', 'Schlotzskys'),
('a0000000-0000-0000-0000-000000000001', '100896', 'Marshall', '1600 E End Blvd', 'Marshall', 'TX', 'Texas', 'Schlotzskys'),

-- Insert Popeyes stores
('a0000000-0000-0000-0000-000000000001', '11496', 'Daphne', '1511 US-98', 'Daphne', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '11817', 'Foley', '1710 S McKenzie St', 'Foley', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '11874', 'Brewton', '487 South Blvd', 'Brewton', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '12262', 'Atmore', '108 Wind River Rd. N.', 'Atmore', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '13215', 'Jackson', '4011 N. College Ave.', 'Jackson', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '13255', 'Andalusia', '461 Western Bypass', 'Andalusia', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '13834', 'Spanish Fort', '30765 Mill Lane', 'Spanish Fort', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '5302', 'Sylacauga', '41260 US Highway 280', 'Sylacauga', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '5742', 'Pelham', '3300 Pelham Pkwy', 'Pelham', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '11138', 'Center Point', '1845 Center Point Pkwy', 'Center Point', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '10576', 'Northport', '2450 McFarland Blvd', 'Northport', 'AL', 'Alabama', 'Popeyes'),
('a0000000-0000-0000-0000-000000000001', '3712', 'Tuscaloosa', '3712 McFarland Blvd E', 'Tuscaloosa', 'AL', 'Alabama', 'Popeyes');
