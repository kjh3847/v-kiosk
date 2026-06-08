-- 푸드코트 키오스크 DB 초기 설정
-- 실행 방법: mysql -u root -p < init_db.sql
-- AWS RDS나 새 서버에 올릴 때 이 파일 한 번만 실행하면 됨

CREATE DATABASE IF NOT EXISTS kiosk_db
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE kiosk_db;

-- 영업일 세션 (개점/마감 단위)
CREATE TABLE IF NOT EXISTS business_sessions (
  session_id    INT          NOT NULL AUTO_INCREMENT,
  open_date     DATE         NOT NULL,
  opened_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  closed_at     DATETIME     DEFAULT NULL,
  status        ENUM('open','closed') DEFAULT 'open',
  total_revenue INT          DEFAULT 0,
  total_orders  INT          DEFAULT 0,
  PRIMARY KEY (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 주문 (결제 완료 기준 1건)
CREATE TABLE IF NOT EXISTS orders ( 
  order_id       INT          NOT NULL AUTO_INCREMENT,
  order_number   INT          NOT NULL,
  store          VARCHAR(50)  NOT NULL,
  payment_method VARCHAR(20)  NOT NULL,
  total_price    INT          NOT NULL,
  ordered_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  session_id     INT          DEFAULT NULL,
  PRIMARY KEY (order_id),
  FOREIGN KEY (session_id) REFERENCES business_sessions(session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 주문 상세 (메뉴별 수량/가격)
CREATE TABLE IF NOT EXISTS order_detail (
  detail_id  INT          NOT NULL AUTO_INCREMENT,
  order_id   INT          NOT NULL,
  menu_id    VARCHAR(100) NOT NULL,
  menu_name  VARCHAR(100) NOT NULL,
  quantity   INT          NOT NULL,
  price      INT          NOT NULL,
  PRIMARY KEY (detail_id),
  FOREIGN KEY (order_id) REFERENCES orders(order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
